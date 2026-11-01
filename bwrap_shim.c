#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/prctl.h>
#include <signal.h>

/*
 * Bubblewrap Compatibility Shim for Flatpak
 * Nested user namespaces are not available inside a Flatpak sandbox, so this
 * shim does NOT create a sandbox. It honours the options that only affect the
 * child process (--argv0, --chdir, --die-with-parent, --setenv, --unsetenv,
 * --clearenv) and ignores every mount / namespace option. Commands run with
 * the permissions of the surrounding Flatpak sandbox.
 */

int main(int argc, char *argv[]) {
    if (argc >= 2) {
        if (strcmp(argv[1], "--version") == 0) {
            printf("bubblewrap 0.11.1\n");
            return 0;
        }
        if (strcmp(argv[1], "--help") == 0) {
            printf("bubblewrap compatibility shim for Flatpak\n");
            return 0;
        }
    }

    const char *argv0 = NULL;
    int die_with_parent = 0;
    int cmd_idx = -1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--argv0") == 0 && i + 1 < argc) {
            argv0 = argv[++i];
        } else if (strcmp(argv[i], "--die-with-parent") == 0) {
            die_with_parent = 1;
        } else if (strcmp(argv[i], "--chdir") == 0 && i + 1 < argc) {
            if (chdir(argv[++i]) != 0) {
                perror("chdir");
            }
        } else if (strcmp(argv[i], "--setenv") == 0 && i + 2 < argc) {
            if (setenv(argv[i + 1], argv[i + 2], 1) != 0) {
                perror("setenv");
            }
            i += 2;
        } else if (strcmp(argv[i], "--unsetenv") == 0 && i + 1 < argc) {
            unsetenv(argv[++i]);
        } else if (strcmp(argv[i], "--clearenv") == 0) {
            clearenv();
        } else if (strcmp(argv[i], "--") == 0) {
            cmd_idx = i + 1;
            break;
        }
    }

    if (die_with_parent) {
        prctl(PR_SET_PDEATHSIG, SIGKILL);
    }

    if (cmd_idx >= 0 && cmd_idx < argc) {
        char *target = argv[cmd_idx];
        if (argv0) {
            argv[cmd_idx] = (char *)argv0;
        }
        execvp(target, &argv[cmd_idx]);
        perror("execvp");
        return 127;
    }

    fprintf(stderr, "bwrap shim: missing '--' command separator\n");
    return 1;
}
