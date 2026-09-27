import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;

public class Dec2 extends GhidraScript {
    DecompInterface di;
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a)
            + "  completed=" + (res!=null && res.decompileCompleted()));
        if (res != null && !res.decompileCompleted())
            println("   err: " + res.getErrorMessage());
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        for (long a : new long[]{0x29f8L, 0x2bacL, 0x7e18L}) dec(a);
    }
}
