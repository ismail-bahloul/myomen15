import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
public class Dec5 extends GhidraScript {
    DecompInterface di;
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f==null) { println("no FUN"); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a));
        if (res!=null && res.getDecompiledFunction()!=null) println(res.getDecompiledFunction().getC());
    }
    public void run() throws Exception { di=new DecompInterface(); di.openProgram(currentProgram); dec(0xb8acL); }
}
