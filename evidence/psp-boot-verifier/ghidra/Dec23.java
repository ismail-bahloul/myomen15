// Dec23.java -- the TOS TA loader / property surface.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec23 extends GhidraScript {
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
    void dec(long a, int t) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, t, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a) + " size=0x"
            + Long.toHexString(f.getBody().getNumAddresses()));
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        callers(0x16748L);
        callers(0x126e8L);
        dec(0x126e8L, 120);   // GP property lookup
        dec(0x16748L, 240);   // TA loader / router
    }
}
