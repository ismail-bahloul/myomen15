// Dec11.java -- who can reach FUN_000083b0, and how the (buffer,size) pair is bounded.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec11 extends GhidraScript {
    DecompInterface di;
    void callers(long a) {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        println("---- callers of " + f.getName() + " (0x" + Long.toHexString(a) + ")");
        int n = 0;
        for (Reference r : getReferencesTo(f.getEntryPoint())) {
            Function c = getFunctionContaining(r.getFromAddress());
            println("   " + (c == null ? "-" : c.toString())
                + "  @0x" + Long.toHexString(r.getFromAddress().getOffset()));
            n++;
        }
        if (n == 0) println("   (no resolved callers)");
    }
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a));
        if (res != null && res.getDecompiledFunction() != null) {
            println(res.getDecompiledFunction().getC());
        } else { println("   (fail)"); }
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        callers(0x738cL);
        callers(0x83b0L);
        dec(0x738cL);   // (addr,size) pair validator, used before FUN_000083b0
        dec(0x148cL);   // descriptor resolve inside FUN_000083b0
        dec(0xdea0L);   // copy 0x100
        dec(0x7332L);   // the other branch of command 0x2d (types 0x60/0x63/0x68)
        dec(0x705cL);   // command 0x28 handler
    }
}
