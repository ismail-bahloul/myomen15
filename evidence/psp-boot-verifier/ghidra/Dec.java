import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec extends GhidraScript {
    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN at 0x" + Long.toHexString(a)); return; }
        println("==== " + f.getName() + " @0x" + Long.toHexString(a));
        for (Reference r : getReferencesTo(f.getEntryPoint()))
            println("   caller 0x" + Long.toHexString(r.getFromAddress().getOffset())
                + "  " + getFunctionContaining(r.getFromAddress()));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        DecompileResults res = di.decompileFunction(f, 60, monitor);
        if (res != null && res.decompileCompleted())
            println(res.getDecompiledFunction().getC());
        else println("   (decompile failed)");
    }
    public void run() throws Exception {
        dec(0x29f8L);   // CryptoModExp wrapper
        dec(0x539cL);   // PSPDirectorySearch
    }
}
