// Dec13.java -- find code that references the OID table and the $PS1 occurrences.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import java.util.*;

public class Dec13 extends GhidraScript {
    DecompInterface di;
    Set<Long> done = new HashSet<>();
    void refTo(long a) throws Exception {
        println("============ refs to 0x" + Long.toHexString(a));
        Reference[] refs = getReferencesTo(toAddr(a));
        if (refs == null || refs.length == 0) { println("   (none)"); return; }
        for (Reference r : refs) {
            Function c = getFunctionContaining(r.getFromAddress());
            println("   from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                + "  " + (c == null ? "-" : c.getName()) + "  (" + r.getReferenceType() + ")");
            if (c != null) done.add(c.getEntryPoint().getOffset());
        }
    }
    void decAll() throws Exception {
        for (long a : done) {
            Function f = getFunctionAt(toAddr(a));
            if (f == null) continue;
            println("==== " + f.getName() + " @0x" + Long.toHexString(a));
            DecompileResults res = di.decompileFunction(f, 120, monitor);
            if (res != null && res.getDecompiledFunction() != null)
                println(res.getDecompiledFunction().getC());
        }
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        refTo(0x13708L);   // PKCS#1 OID table
        refTo(0x1372cL);
        refTo(0x712cL);
        refTo(0xbc88L);
        refTo(0x1a530L);
        refTo(0x1ab60L);
        refTo(0x1e010L);
        println("############ decompiling referencing functions");
        decAll();
    }
}
