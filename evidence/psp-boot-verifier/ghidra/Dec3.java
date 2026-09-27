import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec3 extends GhidraScript {
    DecompInterface di;
    void callers(long a) {
        Function f = getFunctionAt(toAddr(a));
        if (f==null) { println("no FUN 0x"+Long.toHexString(a)); return; }
        println("---- callers of " + f.getName());
        for (Reference r : getReferencesTo(f.getEntryPoint())) {
            Function c = getFunctionContaining(r.getFromAddress());
            println("   " + c + "  @0x" + Long.toHexString(r.getFromAddress().getOffset()));
        }
    }
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f==null) { println("no FUN 0x"+Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a));
        if (res!=null && res.getDecompiledFunction()!=null) println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }
    public void run() throws Exception {
        di = new DecompInterface(); di.openProgram(currentProgram);
        callers(0x2bacL);
        callers(0x2d3cL);
        dec(0x3234L);   // digest compare
        dec(0x2d3cL);   // get expected digest info
    }
}
