// Dec12.java -- locate the RSA verifier and the $PS1 parsers inside DRIVER_ENTRIES.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec12 extends GhidraScript {
    DecompInterface di;
    void at(long a) throws Exception {
        Function f = getFunctionContaining(toAddr(a));
        if (f == null) { println("no function containing 0x" + Long.toHexString(a)); return; }
        println("============ 0x" + Long.toHexString(a) + " is in " + f.getName()
            + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()));
        println("---- callers:");
        for (Reference r : getReferencesTo(f.getEntryPoint())) {
            Function c = getFunctionContaining(r.getFromAddress());
            println("   " + (c == null ? "-" : c.toString())
                + " @0x" + Long.toHexString(r.getFromAddress().getOffset()));
        }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        at(0x13708L);   // PKCS#1 OID table
        at(0x712cL);    // "$PS1"
        at(0xbc88L);    // "$PS1"
        at(0x1a530L);   // "$PS1"
        at(0x1e010L);   // "$PS1"
    }
}
