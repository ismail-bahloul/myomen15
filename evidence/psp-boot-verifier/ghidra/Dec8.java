// Dec8.java -- the top of the boot flow and the directory search it uses.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec8 extends GhidraScript {
    DecompInterface di;

    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a));
        if (res != null && res.getDecompiledFunction() != null) {
            println(res.getDecompiledFunction().getC());
        } else {
            println("   (fail)");
        }
    }

    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        dec(0x73e8L);   // top of the tree (no resolved callers)
        dec(0x3eb8L);   // directory search returning an entry by EntryType
        dec(0xb760L);   // expected-digest getter for mode 2
        dec(0x48c4L);   // boot-mode dispatch
        dec(0x2bacL);   // the full PKCS#1 v1.5 verifier (for comparison)
    }
}
