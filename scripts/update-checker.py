#!/usr/bin/env python3
"""
ChatGPT Flatpak Automated Upstream Update Checker

Checks the upstream OpenAI Linux YUM/RPM repository for new releases,
fetches the official package SHA-256 and metadata from primary.xml.gz,
and updates the Flatpak manifest (com.openai.chatgpt.yaml) and AppStream metadata.
"""

import os
import re
import sys
import gzip
import json
import argparse
import datetime
import subprocess
import urllib.request
import xml.etree.ElementTree as ET

REPO_BASE_URL = "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/x86_64"
REPOMD_URL = f"{REPO_BASE_URL}/repodata/repomd.xml"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO_ROOT, "com.openai.chatgpt.yaml")
METAINFO_PATH = os.path.join(REPO_ROOT, "com.openai.chatgpt.metainfo.xml")

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def fetch_url(url, timeout=30):
    """Fetch URL using curl (handles Cloudflare TLS fingerprinting and proxies)."""
    cmd = ["curl", "-sSL", "--fail", "--connect-timeout", "15", "-m", str(timeout)]

    # Add proxy if specified or if local standard proxy is running and no env proxy set
    proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy") or os.environ.get("all_proxy")
    if not proxy:
        # Check if local clash/mihomo proxy is listening
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", 7890)) == 0:
                    proxy = "http://127.0.0.1:7890"
        except Exception:
            pass

    if proxy:
        cmd.extend(["-x", proxy])

    cmd.append(url)
    return subprocess.check_output(cmd)


def fetch_latest_upstream_release():
    """Fetch and parse OpenAI YUM repository repodata."""
    print(f"Fetching repository metadata: {REPOMD_URL}")
    repomd_xml = fetch_url(REPOMD_URL)
    repomd_root = ET.fromstring(repomd_xml)

    # XML namespace for repomd
    ns = {"repo": "http://linux.duke.edu/metadata/repo"}
    primary_location = None

    for data in repomd_root.findall("repo:data", ns):
        if data.attrib.get("type") == "primary":
            loc = data.find("repo:location", ns)
            if loc is not None:
                primary_location = loc.attrib.get("href")
                break

    if not primary_location:
        raise RuntimeError("Could not find primary.xml.gz location in repomd.xml")

    primary_url = f"{REPO_BASE_URL}/{primary_location}"
    print(f"Fetching primary package catalog: {primary_url}")
    compressed_data = fetch_url(primary_url)
    primary_xml = gzip.decompress(compressed_data)

    # Parse primary.xml
    p_ns = {
        "common": "http://linux.duke.edu/metadata/common",
        "rpm": "http://linux.duke.edu/metadata/rpm"
    }
    p_root = ET.fromstring(primary_xml)

    latest_pkg = None
    for pkg in p_root.findall("common:package", p_ns):
        name_elem = pkg.find("common:name", p_ns)
        if name_elem is not None and name_elem.text == "chatgpt":
            version_elem = pkg.find("common:version", p_ns)
            checksum_elem = pkg.find("common:checksum", p_ns)
            location_elem = pkg.find("common:location", p_ns)
            time_elem = pkg.find("common:time", p_ns)

            ver = version_elem.attrib.get("ver")
            rel = version_elem.attrib.get("rel")
            sha256 = checksum_elem.text.strip()
            href = location_elem.attrib.get("href")
            build_time = int(time_elem.attrib.get("build", 0))

            latest_pkg = {
                "version": ver,
                "release": rel,
                "full_version": f"{ver}-{rel}",
                "sha256": sha256,
                "rpm_url": f"{REPO_BASE_URL}/{href}",
                "filename": href,
                "build_time": build_time,
                "date": datetime.datetime.fromtimestamp(build_time, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            }
            break

    if not latest_pkg:
        raise RuntimeError("No chatgpt package entry found in primary metadata")

    return latest_pkg


def parse_current_manifest():
    """Parse the current version, URL, and sha256 from the manifest."""
    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    url_match = re.search(r"url:\s*(https?://[^\s]+/chatgpt-([0-9.]+)-([0-9]+)\.x86_64\.rpm)", content)
    sha_match = re.search(r"sha256:\s*([a-f0-9]{64})", content)

    if not url_match or not sha_match:
        raise ValueError("Could not parse current package URL or sha256 from manifest")

    return {
        "url": url_match.group(1),
        "version": url_match.group(2),
        "release": url_match.group(3),
        "full_version": f"{url_match.group(2)}-{url_match.group(3)}",
        "sha256": sha_match.group(1),
        "content": content
    }


def update_manifest(old_content, new_url, new_sha):
    """Replace URL and sha256 in manifest."""
    content = re.sub(
        r"url:\s*https?://[^\s]+/chatgpt-[0-9.]+-([0-9]+)\.x86_64\.rpm",
        f"url: {new_url}",
        old_content
    )
    content = re.sub(
        r"sha256:\s*[a-f0-9]{64}",
        f"sha256: {new_sha}",
        content
    )
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated manifest at {MANIFEST_PATH}")


def update_metainfo(new_version, release_date=None):
    """Add new release to com.openai.chatgpt.metainfo.xml if not present."""
    if not os.path.exists(METAINFO_PATH):
        print(f"Metainfo file not found: {METAINFO_PATH}")
        return

    with open(METAINFO_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if f'release version="{new_version}"' in content:
        print(f"Metainfo already has release entry for version {new_version}")
        return

    if release_date is None:
        release_date = datetime.date.today().isoformat()

    new_release_tag = (
        f'    <release version="{new_version}" date="{release_date}">\n'
        f'      <description>\n'
        f'        <p>Upstream ChatGPT Linux client version {new_version}.</p>\n'
        f'      </description>\n'
        f'    </release>'
    )

    if "<releases>" in content:
        content = content.replace("<releases>", f"<releases>\n{new_release_tag}", 1)
        with open(METAINFO_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Added release {new_version} to {METAINFO_PATH}")


def set_github_output(outputs):
    """Write outputs to $GITHUB_OUTPUT file for GitHub Actions."""
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output and os.path.exists(gh_output):
        with open(gh_output, "a", encoding="utf-8") as f:
            for k, v in outputs.items():
                f.write(f"{k}={v}\n")


def main():
    parser = argparse.ArgumentParser(description="ChatGPT Flatpak update checker")
    parser.add_argument("--check", action="store_true", help="Only check for updates without modifying files")
    parser.add_argument("--update", action="store_true", help="Perform the update if new version found")
    parser.add_argument("--force", action="store_true", help="Force recalculation and update even if up to date")
    parser.add_argument("--ci", action="store_true", help="Output GitHub Actions step variables")

    args = parser.parse_args()

    latest = fetch_latest_upstream_release()
    print(f"Upstream latest release: version {latest['version']} (release: {latest['release']})")
    print(f"  Package: {latest['filename']}")
    print(f"  SHA-256: {latest['sha256']}")
    print(f"  Date:    {latest['date']}")

    curr = parse_current_manifest()
    print(f"Current manifest release: version {curr['version']} (release: {curr['release']})")

    needs_update = (
        latest["full_version"] != curr["full_version"]
        or latest["sha256"] != curr["sha256"]
        or args.force
    )

    if not needs_update:
        print(f"Manifest is already up-to-date with latest release {latest['version']}.")
        if args.ci:
            set_github_output({
                "updated": "false",
                "version": curr["version"],
                "release": curr["release"]
            })
        return 0

    print(f"Update available: {curr['full_version']} -> {latest['full_version']}")
    print(f"Target URL: {latest['rpm_url']}")

    if args.check:
        print("Check mode only. Manifest not updated.")
        if args.ci:
            set_github_output({
                "updated": "true",
                "version": latest["version"],
                "release": latest["release"],
                "rpm_url": latest["rpm_url"],
                "sha256": latest["sha256"]
            })
        return 0

    update_manifest(curr["content"], latest["rpm_url"], latest["sha256"])
    update_metainfo(latest["version"], latest["date"])

    if args.ci:
        set_github_output({
            "updated": "true",
            "version": latest["version"],
            "release": latest["release"],
            "rpm_url": latest["rpm_url"],
            "sha256": latest["sha256"]
        })

    print("Successfully updated files for new release.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
