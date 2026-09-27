// Dec15.java -- the verifier callers (the load/verify routines) in DRIVER_ENTRIES.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec15 extends GhidraScript {
    DecompInterface di;
    void callers(long a) {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        println("---- callers of " + f.getName() + " (0x" + Long.toHexString(a) + ")");
        int n = 0;
        for (Reference r : getReferencesTo(f.getEntryPoint())) {
            Function c = getFunctionContaining(r.getFromAddress());
            println("   " + (c == null ? "-" : c.getName()) + " @0x"
                + Long.toHexString(r.getFromAddress().getOffset()));
            n++;
        }
        if (n == 0) println("   (none)");
    }
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a));
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        callers(0x17e10L);
        callers(0xa828L);
        callers(0x1a7c4L);
        dec(0x17e10L);   // caller of the RSA verify
        dec(0xa828L);    // caller of the $PS1 users bc20 / 1a3b8
        dec(0xbc20L);    // $PS1 user
        dec(0x1a3b8L);   // $PS1 user
        dec(0xc558L);    // helper in FUN_00007000
    }
}
