// Dec24.java -- are the $PS1 bytes in TOS code? plus the other property getters.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;

public class Dec24 extends GhidraScript {
    DecompInterface di;
    void where(long a) throws Exception {
        Function f = getFunctionContaining(toAddr(a));
        println("0x" + Long.toHexString(a) + "  in " + (f == null ? "(no function)" : f.getName()
            + " @0x" + Long.toHexString(f.getEntryPoint().getOffset())));
        if (f != null && !done.contains(f.getEntryPoint().getOffset())) {
            done.add(f.getEntryPoint().getOffset());
            DecompileResults res = di.decompileFunction(f, 120, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset())
                + " size=0x" + Long.toHexString(f.getBody().getNumAddresses()));
            if (res != null && res.getDecompiledFunction() != null)
                println(res.getDecompiledFunction().getC());
        }
    }
    java.util.Set<Long> done = new java.util.HashSet<>();
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a) + " size=0x"
            + Long.toHexString(f.getBody().getNumAddresses()));
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
    }
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        where(0x16120L);
        where(0x173a0L);
        where(0x17538L);
        dec(0x146fcL);   // property getter
        dec(0x147c8L);   // property getter
    }
}
