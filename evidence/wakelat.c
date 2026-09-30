/* wakelat.c — scheduler wake-up latency under load.
 *   usage: ./wakelat <seconds> <sleepers>
 * Each sleeper does nanosleep(1 ms) in a loop and records how late it woke
 * (actual - requested). Run it beside an all-core load: that is where a
 * scheduler's latency handling shows, and where an idle machine shows nothing.
 * Prints p50/p99/p99.9/max in microseconds over all sleepers.
 *   gcc -O2 -pthread -o wakelat wakelat.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <time.h>

#define MAXS 200000
static double dur;
static double *lat[64];
static int nlat[64];

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

static void *sleeper(void *a) {
    int id = (int)(long)a;
    lat[id] = malloc(sizeof(double) * MAXS);
    double end = now() + dur;
    struct timespec req = {0, 1000000};
    while (now() < end && nlat[id] < MAXS) {
        double t0 = now();
        nanosleep(&req, NULL);
        lat[id][nlat[id]++] = (now() - t0 - 0.001) * 1e6;
    }
    return NULL;
}
static int cmp(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return (x > y) - (x < y); }

int main(int argc, char **argv) {
    dur = argc > 1 ? atof(argv[1]) : 20;
    int n = argc > 2 ? atoi(argv[2]) : 4;
    pthread_t th[64];
    for (long i = 0; i < n; i++) pthread_create(&th[i], NULL, sleeper, (void *)i);
    for (int i = 0; i < n; i++) pthread_join(th[i], NULL);
    long total = 0; for (int i = 0; i < n; i++) total += nlat[i];
    double *all = malloc(sizeof(double) * total); long k = 0;
    for (int i = 0; i < n; i++) for (int j = 0; j < nlat[i]; j++) all[k++] = lat[i][j];
    qsort(all, total, sizeof(double), cmp);
    printf("wakes=%ld p50=%.0f p99=%.0f p99.9=%.0f max=%.0f us\n", total,
           all[total / 2], all[(long)(total * 0.99)], all[(long)(total * 0.999)], all[total - 1]);
    return 0;
}
