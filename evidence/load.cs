using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

// Generateur de charge all-core reproductible.
// Usage: load.exe <warmupSec> <measureSec> <outFile>
class Load
{
    static volatile bool _stop;
    static long _iters;
    static readonly object Lk = new object();

    static void Worker()
    {
        double x = 1.0001;
        long acc = 0;
        long local = 0;
        while (!_stop)
        {
            for (long i = 0; i < 2000000; i++)
            {
                x = x * 1.0000001 + 0.9999999;
                if (x > 3.0) x *= 0.5;
                acc += i ^ (long)x;
            }
            local += 2000000;
            Interlocked.Add(ref _iters, 2000000);
        }
        GC.KeepAlive(acc);
    }

    static void Main(string[] args)
    {
        int warmup = args.Length > 0 ? int.Parse(args[0]) : 20;
        int measure = args.Length > 1 ? int.Parse(args[1]) : 40;
        string outFile = args.Length > 2 ? args[2] : "load_result.txt";
        int reqThreads = args.Length > 3 ? int.Parse(args[3]) : 0;
        int threads = reqThreads > 0 ? reqThreads : Environment.ProcessorCount;

        var tasks = new Task[threads];
        for (int t = 0; t < threads; t++)
            tasks[t] = Task.Factory.StartNew(Worker, TaskCreationOptions.LongRunning);

        Thread.Sleep(warmup * 1000);
        var swM = Stopwatch.StartNew();
        long before = Interlocked.Read(ref _iters);
        Thread.Sleep(measure * 1000);
        swM.Stop();
        long after = Interlocked.Read(ref _iters);
        _stop = true;
        Task.WaitAll(tasks);

        double secs = swM.Elapsed.TotalSeconds;
        long done = after - before;
        File.WriteAllText(outFile,
            "threads=" + threads + "\n" +
            "iterations=" + done + "\n" +
            "measure_s=" + secs.ToString("F2") + "\n" +
            "throughput_Mi_s=" + (done / 1e6 / secs).ToString("F1") + "\n");
    }
}
