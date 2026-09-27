// Dec18.java -- the driver entry and its dispatcher in DRIVER_ENTRIES.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec18 extends GhidraScript {
    DecompInterface di;
    void dec(long a, int t) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, t, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a)
            + "  size=0x" + Long.toHexString(f.getBody().getNumAddresses()));
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        dec(0x77e0L, 120);   // driver entry (root)
        dec(0xdbe0L, 240);   // dispatcher
    }
}
