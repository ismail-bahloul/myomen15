// Dec22.java -- boot loader command handlers that take host addresses (SMN/register).
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;

public class Dec22 extends GhidraScript {
    DecompInterface di;
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a) + " size=0x"
            + Long.toHexString(f.getBody().getNumAddresses()));
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        dec(0xeadcL);   // cmd 0x50/0x35 SMN access check
        dec(0xecccL);   // cmd 0x51 unmap
        dec(0xdca0L);   // cmd 0x59
        dec(0xcaecL);   // cmd 0x4e
        dec(0xd544L);   // cmd 0x35 read size 1
        dec(0xd514L);   // cmd 0x35 read size 2
        dec(0xd52cL);   // cmd 0x35 read size 4
        dec(0x1070L);   // cmd 0x30
        dec(0x5ae4L);   // cmd 0x31
        dec(0xeb20L);   // cmd 0xa9
    }
}
