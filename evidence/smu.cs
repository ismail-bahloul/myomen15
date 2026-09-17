using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

// Outil de lecture/ecriture SMU pour Ryzen 7 5800H (Cezanne) via PawnIO + module RyzenSMU.
// Usage:
//   smu.exe info
//   smu.exe co <offset>              (set-coall = msg 0x55, encodage UXTU)
//   smu.exe send <msg> [a1..a6]
//   smu.exe read <addr_hex>
//   smu.exe pm <sortie.bin>
class SmuTool
{
    [DllImport("PawnIOLib.dll", CallingConvention = CallingConvention.StdCall)]
    static extern int pawnio_open(out IntPtr handle);

    [DllImport("PawnIOLib.dll", CallingConvention = CallingConvention.StdCall)]
    static extern int pawnio_load(IntPtr handle, byte[] blob, UIntPtr size);

    [DllImport("PawnIOLib.dll", CallingConvention = CallingConvention.StdCall)]
    static extern int pawnio_execute(IntPtr handle, string name, ulong[] inBuf, UIntPtr inSize,
                                     ulong[] outBuf, UIntPtr outSize, out UIntPtr returnSize);

    [DllImport("PawnIOLib.dll", CallingConvention = CallingConvention.StdCall)]
    static extern int pawnio_close(IntPtr handle);

    static IntPtr h = IntPtr.Zero;
    static int LastHr;
    static bool useBytes = false;

    const string ModulePath =
        @"C:\Program Files\JamesCJ60\Universal x86 Tuning Utility\Assets\AMD\PawnIO\RyzenSMU.bin";

    static void Usage()
    {
        Console.WriteLine("usage:");
        Console.WriteLine("  smu.exe info");
        Console.WriteLine("  smu.exe co <offset>");
        Console.WriteLine("  smu.exe send <msg> [a1..a6]");
        Console.WriteLine("  smu.exe read <addr_hex>");
        Console.WriteLine("  smu.exe pm <outfile>");
    }

    static string HrName(int hr)
    {
        uint u = (uint)hr;
        switch (u)
        {
            case 0x00000000: return "STATUS_SUCCESS (SMU_OK)";
            case 0xC0000003: return "SMU_UnknownCmd (commande inconnue)";
            case 0x80000011: return "SMU_CmdRejectedBusy (SMU occupe)";
            case 0xC0000001: return "SMU_CmdRejectedPrereq / SMU_Failed";
            case 0xC0000002: return "STATUS_NOT_IMPLEMENTED";
            case 0xC000000D: return "STATUS_INVALID_PARAMETER (taille in/out)";
            case 0xC00000B5: return "STATUS_IO_TIMEOUT (aucune reponse SMU)";
            case 0xC00000BB: return "STATUS_NOT_SUPPORTED";
            default: return "0x" + u.ToString("X8");
        }
    }

    static ulong[] Exec(string name, ulong[] inBuf, int outCount)
    {
        ulong[] outBuf = new ulong[outCount < 1 ? 1 : outCount];
        UIntPtr inSize = useBytes ? new UIntPtr((uint)(inBuf.Length * 8)) : new UIntPtr((uint)inBuf.Length);
        UIntPtr outSize = useBytes ? new UIntPtr((uint)(outBuf.Length * 8)) : new UIntPtr((uint)outBuf.Length);
        UIntPtr ret;
        LastHr = pawnio_execute(h, name, inBuf, inSize, outBuf, outSize, out ret);
        return outBuf;
    }

    static uint EncodeCO(int offset)
    {
        if (offset >= 0) return (uint)offset;
        long n = -(long)offset;
        if (n > 1048576) throw new ArgumentOutOfRangeException("offset");
        return (uint)(1048576 - n);
    }

    static IntPtr mutex = IntPtr.Zero; // placeholder (non utilise, cf. Mutex .NET)

    static Mutex AcquirePci()
    {
        try
        {
            Mutex m = new Mutex(false, "Global\\Access_PCI");
            m.WaitOne(5000);
            return m;
        }
        catch { return null; }
    }

    static int Main(string[] args)
    {
        if (args.Length == 0) { Usage(); return 1; }

        IntPtr handle;
        int hr = pawnio_open(out handle);
        if (hr != 0) { Console.WriteLine("pawnio_open -> 0x" + ((uint)hr).ToString("X8")); return 2; }
        h = handle;

        byte[] blob = File.ReadAllBytes(ModulePath);
        hr = pawnio_load(h, blob, new UIntPtr((uint)blob.Length));
        if (hr != 0)
        {
            Console.WriteLine("pawnio_load -> 0x" + ((uint)hr).ToString("X8"));
            return 3;
        }

        string cmd = args[0].ToLowerInvariant();

        if (cmd == "info")
        {
            // auto-detection du mode de taille (elements vs octets)
            ulong[] o = Exec("ioctl_get_code_name", new ulong[0], 1);
            if (LastHr == unchecked((int)0xC000000D))
            {
                useBytes = true;
                Console.WriteLine("[i] tailles en OCTETS");
                o = Exec("ioctl_get_code_name", new ulong[0], 1);
            }
            else
            {
                Console.WriteLine("[i] tailles en ELEMENTS");
            }
            Console.WriteLine("ioctl_get_code_name  -> " + HrName(LastHr) + "  code_name=" + o[0]);

            o = Exec("ioctl_get_smu_version", new ulong[0], 1);
            Console.WriteLine("ioctl_get_smu_version-> " + HrName(LastHr) + "  smu_version=0x" + o[0].ToString("X8") +
                              " (" + o[0] + ")");

            Mutex m = AcquirePci();
            o = Exec("ioctl_resolve_pm_table", new ulong[0], 2);
            Console.WriteLine("ioctl_resolve_pm_table-> " + HrName(LastHr) + "  pm_version=0x" + o[0].ToString("X8") +
                              "  base=0x" + o[1].ToString("X8"));
            if (m != null) { try { m.ReleaseMutex(); } catch { } m.Close(); }
            return 0;
        }

        if (cmd == "co")
        {
            int off = int.Parse(args[1]);
            uint enc = EncodeCO(off);
            ulong[] inb = new ulong[7];
            inb[0] = 0x55;          // set-coall (Cezanne)
            inb[1] = enc;
            ulong[] o = Exec("ioctl_send_smu_command", inb, 6);
            Console.WriteLine("set-coall offset=" + off + " -> arg=0x" + enc.ToString("X8"));
            Console.WriteLine("  SMU repond: " + HrName(LastHr));
            Console.WriteLine("  out: " + Join(o));
            return 0;
        }

        if (cmd == "send")
        {
            ulong[] inb = new ulong[7];
            inb[0] = ParseNum(args[1]);
            for (int i = 0; i < 6; i++)
                inb[i + 1] = (args.Length > 2 + i) ? ParseNum(args[2 + i]) : 0UL;
            ulong[] o = Exec("ioctl_send_smu_command", inb, 6);
            Console.WriteLine("send msg=0x" + inb[0].ToString("X") + " args=" + Join(inb) +
                              "\n  SMU repond: " + HrName(LastHr) + "\n  out: " + Join(o));
            return 0;
        }

        if (cmd == "read")
        {
            ulong[] inb = new ulong[1];
            inb[0] = ParseNum(args[1]);
            Mutex m = AcquirePci();
            ulong[] o = Exec("ioctl_read_smu_register", inb, 1);
            Console.WriteLine("read 0x" + inb[0].ToString("X8") + " -> " + HrName(LastHr) +
                              "  valeur=0x" + o[0].ToString("X8") + " (" + o[0] + ")");
            if (m != null) { try { m.ReleaseMutex(); } catch { } m.Close(); }
            return 0;
        }

        if (cmd == "pm")
        {
            string outFile = args.Length > 1 ? args[1] : "pmtable.bin";
            Mutex m = AcquirePci();
            ulong[] o = Exec("ioctl_resolve_pm_table", new ulong[0], 2);
            Console.WriteLine("resolve -> " + HrName(LastHr) + "  version=0x" + o[0].ToString("X8") +
                              "  base=0x" + o[1].ToString("X8"));
            if (LastHr != 0) { if (m != null) { m.ReleaseMutex(); m.Close(); } return 4; }

            ulong[] dummy = new ulong[1];
            ulong[] outBuf = new ulong[1024];
            UIntPtr ret;
            bool any = false;

            // Le SMU doit d'abord TRANSFERER la table en DRAM (ioctl_update_pm_table),
            // sinon la lecture ne renvoie que des zeros.
            for (int attempt = 1; attempt <= 4; attempt++)
            {
                LastHr = pawnio_execute(h, "ioctl_update_pm_table", new ulong[0], new UIntPtr(0), dummy, new UIntPtr(0), out ret);
                Console.WriteLine("  update_pm_table #" + attempt + " -> " + HrName(LastHr));
                if (LastHr != 0) break;
                System.Threading.Thread.Sleep(400);

                UIntPtr outSize = useBytes ? new UIntPtr((uint)(outBuf.Length * 8)) : new UIntPtr((uint)outBuf.Length);
                LastHr = pawnio_execute(h, "ioctl_read_pm_table", new ulong[0], new UIntPtr(0), outBuf, outSize, out ret);
                any = false;
                for (int i = 0; i < outBuf.Length; i++) { if (outBuf[i] != 0) { any = true; break; } }
                Console.WriteLine("  read_pm_table #" + attempt + " -> " + HrName(LastHr) +
                                  "  elements=" + (ulong)ret + "  non-zero=" + (any ? "OUI" : "non"));
                if (LastHr != 0 || any) break;
            }

            if (LastHr == 0 && any)
            {
                byte[] bytes = new byte[outBuf.Length * 8];
                Buffer.BlockCopy(outBuf, 0, bytes, 0, bytes.Length);
                File.WriteAllBytes(outFile, bytes);
                Console.WriteLine("ecrit " + bytes.Length + " octets dans " + outFile);
                Console.Write("32 premiers dwords: ");
                for (int i = 0; i < 32; i++) Console.Write(outBuf[i].ToString("X8") + " ");
                Console.WriteLine();
            }
            if (m != null) { try { m.ReleaseMutex(); } catch { } m.Close(); }
            return 0;
        }

        Usage();
        return 1;
    }

    static ulong ParseNum(string s)
    {
        if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) return Convert.ToUInt64(s.Substring(2), 16);
        return ulong.Parse(s);
    }

    static string Join(ulong[] a)
    {
        string r = "";
        for (int i = 0; i < a.Length; i++) r += (i > 0 ? ", " : "") + "0x" + a[i].ToString("X");
        return r;
    }
}
