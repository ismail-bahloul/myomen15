// Dec7.java -- root the chain above FUN_0000b8ac and decode the primitives it uses.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec7 extends GhidraScript {
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
        } else {
            println("   (fail)");
        }
    }

    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        callers(0x48c4L);
        callers(0x83b0L);
        callers(0x73e8L);
        callers(0xb8acL);
        callers(0x2b2cL);
        dec(0xaa48L);   // loads an entry by EntryType, then calls FUN_0000b8ac
        dec(0x2b2cL);   // PKCS#1 verify actually used by FUN_0000bad8
        dec(0x25ecL);   // alternate verify primitive (HMAC/16-byte)
        dec(0xca04L);   // reads the signed body
        dec(0x7fdcL);   // parses key descriptor at header+0x80
        dec(0x83b0L);   // the other caller of FUN_0000b8ac
    }
}
