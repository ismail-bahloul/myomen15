// Dec19.java -- the four load-and-verify routines reached from host commands.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec19 extends GhidraScript {
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
        println("==== " + f.getName() + " @0x" + Long.toHexString(a) + " size=0x"
            + Long.toHexString(f.getBody().getNumAddresses()));
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        callers(0x106dcL);
        callers(0x119a0L);
        callers(0x16c80L);
        dec(0x106dcL);   // host command 0x3130 -> entry verify
        dec(0x119a0L);
        dec(0x16c80L);
        dec(0x1a3b4L);   // host command 0x312d
    }
}
