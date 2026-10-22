#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/prctl.h>
#include <signal.h>

/*
 * Bubblewrap Compatibility Shim for Flatpak
 * Transparently strips nested sandbox flags and forwards commands to the
 * parent Flatpak container environment.
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
