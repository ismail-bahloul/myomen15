// Dec21.java -- candidates: functions sharing the host-map SVCs (0xa7 / 0x6b) with
// the validators but not calling them.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec21 extends GhidraScript {
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
        callers(0x159c8L);
        callers(0x15bf0L);
        callers(0x15eacL);
        callers(0x15facL);
        callers(0x14a5cL);
        dec(0x159c8L);   // svc 0xa7, no validator
        dec(0x15bf0L);   // svc 0xa7
        dec(0x15eacL);   // svc 0xa7
        dec(0x15facL);   // svc 0xa7
        dec(0x14a5cL);   // called by FUN_00011604 after validation
        dec(0x75a0L);    // svc 0x6b/0x6d
        dec(0x161b8L);   // svc 0x6b/0x6d
        dec(0xc4bcL);    // used by FUN_000119a0
    }
}
