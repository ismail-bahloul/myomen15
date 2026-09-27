// Dec6.java -- finish the PSP_FW_BOOT_LOADER HBV verification chain.
// Run: analyzeHeadless <ghproj> PSPBL -process 'd00_e00_PSP_FW_BOOT_LOADER~0x1_0.11.0.85' \
//        -noanalysis -scriptPath <this dir> -postScript Dec6.java
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class Dec6 extends GhidraScript {
    DecompInterface di;

    void callers(long a) {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        println("---- callers of " + f.getName()
            + " (0x" + Long.toHexString(a) + ")");
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
        callers(0xb8acL);
        callers(0xef6cL);
        callers(0xaa48L);
        dec(0xbad8L);   // signature check used by FUN_0000b8ac
        dec(0xe108L);   // key copy/compare against DAT_0000ba88
        dec(0x3a20L);   // alternate validation branch (header+0x78 & 1)
        dec(0x38c4L);   // boot mode / SKU selector
        dec(0xa61cL);   // tail of FUN_0000b8ac
    }
}
