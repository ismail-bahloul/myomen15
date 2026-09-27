// Dec9.java -- key source, image loader, hash used by the generic verifier.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;

public class Dec9 extends GhidraScript {
    DecompInterface di;
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
        dec(0x3e50L);   // key source used by FUN_00002b2c
        dec(0x5194L);   // image loader used by FUN_000048c4
        dec(0x302cL);   // hash used by FUN_0000ef6c
        dec(0x3624L);   // mode fetch for command 0x52
    }
}
