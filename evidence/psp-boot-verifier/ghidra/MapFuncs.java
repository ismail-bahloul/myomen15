import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.*;

public class MapFuncs extends GhidraScript {
    public void run() throws Exception {
        println("lang = " + currentProgram.getLanguageID());
        for (MemoryBlock b : currentProgram.getMemory().getBlocks())
            println("block " + b.getName() + " start=0x" + Long.toHexString(b.getStart().getOffset())
                + " size=0x" + Long.toHexString(b.getSize()) + " X=" + b.isExecute());
        FunctionManager fm = currentProgram.getFunctionManager();
        int n = 0;
        for (Function f : fm.getFunctions(true)) n++;
        println("functions = " + n);
        int i = 0;
        for (Function f : fm.getFunctions(true)) {
            if (i++ < 25) println(String.format("  FUN 0x%x  size=0x%x  %s",
                f.getEntryPoint().getOffset(), f.getBody().getNumAddresses(), f.getName()));
        }
        // references landing in the string region 0x1800..0x6a00
        ReferenceIterator it = currentProgram.getReferenceManager()
            .getReferenceIterator(currentProgram.getMinAddress());
        int hits = 0;
        while (it.hasNext()) {
            Reference r = it.next();
            Address to = r.getToAddress();
            if (to == null) continue;
            long o = to.getOffset();
            if (o >= 0x1800 && o < 0x6a00) {
                if (hits++ < 20) println(String.format("  REF 0x%x -> 0x%x (%s)",
                    r.getFromAddress().getOffset(), o, r.getReferenceType()));
            }
        }
        println("refs into string region = " + hits);
    }
}
