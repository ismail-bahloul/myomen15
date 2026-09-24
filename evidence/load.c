/* load.c — fixed-duration all-core load; usage: ./load <warmup_s> <measure_s> <threads>
 *
 * The same loop as the Windows harness in record/03-open-questions.md, so the
 * throughput number is roughly comparable across the two sides (compiler
 * differences aside). Used here for the joules-per-iteration measurement that
 * section left open.
 *
 *   gcc -O2 -pthread -o load load.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>

static volatile int stop = 0;
static unsigned long long total = 0;
static pthread_mutex_t lk = PTHREAD_MUTEX_INITIALIZER;

static void *worker(void *arg) {
    double x = 1.0001; long acc = 0;
    while (!stop) {
        for (long i = 0; i < 2000000; i++) {
            x = x * 1.0000001 + 0.9999999;
            if (x > 3.0) x *= 0.5;
            acc += i ^ (long)x;
        }
        pthread_mutex_lock(&lk); total += 2000000ULL; pthread_mutex_unlock(&lk);
    }
    __asm__ volatile("" :: "r"(acc) : "memory");
    return NULL;
}

int main(int argc, char **argv) {
    int warmup = argc > 1 ? atoi(argv[1]) : 20;
    int measure = argc > 2 ? atoi(argv[2]) : 40;
    int threads = argc > 3 ? atoi(argv[3]) : (int)sysconf(_SC_NPROCESSORS_ONLN);
    pthread_t th[512];
    for (int i = 0; i < threads && i < 512; i++) pthread_create(&th[i], NULL, worker, NULL);
    sleep(warmup);
    unsigned long long before = total;
    struct timespec t0, t1; clock_gettime(CLOCK_MONOTONIC, &t0);
    sleep(measure);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    unsigned long long done = total - before;
    double secs = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
    stop = 1;
    for (int i = 0; i < threads && i < 512; i++) pthread_join(th[i], NULL);
    printf("threads=%d\niterations=%llu\nmeasure_s=%.2f\nthroughput_Mi_s=%.1f\n",
           threads, done, secs, done / 1e6 / secs);
    return 0;
}
