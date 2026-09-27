// Dec10.java -- the wrapped-image parser and the generic verifier.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;

public class Dec10 extends GhidraScript {
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
        dec(0xef6cL);   // generic verifier (mode 1); calls 302c + 2bac
        dec(0xd7d4L);   // copy into the wrapped-key buffer (FUN_00003a20)
        dec(0xaea0L);   // expected digest/key descriptor source
        dec(0x2606L);   // 16-byte keyed digest (FUN_00007fdc)
        dec(0x11c8L);   // 16-byte MAC body (FUN_000025ec)
        dec(0x8788L);   // header entry-type byte check
        dec(0x1f08L);   // CCP wrapper (FUN_0000302c)
        dec(0x1f22L);   // CCP wrapper (FUN_0000302c)
        dec(0x2d8cL);   // CCP finalize (FUN_0000302c)
    }
}
