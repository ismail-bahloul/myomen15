// MapAll.java -- list every defined string and its xrefs, plus a function census.
// Generic: run against any imported PSP module.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;

public class MapAll extends GhidraScript {
    public void run() throws Exception {
        println("lang = " + currentProgram.getLanguageID());
        for (MemoryBlock b : currentProgram.getMemory().getBlocks())
            println("block " + b.getName() + " 0x" + Long.toHexString(b.getStart().getOffset())
                + " size=0x" + Long.toHexString(b.getSize()) + " X=" + b.isExecute());
        FunctionManager fm = currentProgram.getFunctionManager();
        int n = 0;
        for (Function f : fm.getFunctions(true)) n++;
        println("functions = " + n);
        println("---- functions ----");
        for (Function f : fm.getFunctions(true))
            println(String.format("  FUN 0x%x size=0x%x %s", f.getEntryPoint().getOffset(),
                f.getBody().getNumAddresses(), f.getName()));
        println("---- defined strings with xrefs ----");
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int shown = 0;
        while (it.hasNext()) {
            Data d = it.next();
            if (!d.hasStringValue()) continue;
            Object v = d.getValue();
            if (v == null) continue;
            String s = v.toString();
            if (s.length() < 4) continue;
            Reference[] refs = getReferencesTo(d.getAddress());
            println(String.format("0x%x xrefs=%d  \"%s\"", d.getAddress().getOffset(),
                refs == null ? 0 : refs.length, s.replace('\n', ' ')));
            if (refs != null) for (Reference r : refs) {
                Function f = getFunctionContaining(r.getFromAddress());
                println(String.format("      <- 0x%x  %s  (%s)", r.getFromAddress().getOffset(),
                    f == null ? "-" : f.getName(), r.getReferenceType()));
            }
            if (++shown > 300) { println("  (truncated)"); break; }
        }
    }
}
