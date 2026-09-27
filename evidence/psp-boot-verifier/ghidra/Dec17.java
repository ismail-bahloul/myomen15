// Dec17.java -- upward call graph from the loaders; list root functions.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import java.util.*;

public class Dec17 extends GhidraScript {
    void roots() {
        FunctionManager fm = currentProgram.getFunctionManager();
        println("---- functions with NO callers (candidate entry points / SVC handlers)");
        int n = 0;
        for (Function f : fm.getFunctions(true)) {
            Reference[] refs = getReferencesTo(f.getEntryPoint());
            if (refs == null || refs.length == 0) {
                println(String.format("  ROOT 0x%x  %s  size=0x%x",
                    f.getEntryPoint().getOffset(), f.getName(), f.getBody().getNumAddresses()));
                n++;
            }
        }
        println("  total roots = " + n);
    }

    void up(long start, int maxDepth) {
        println("---- upward BFS from 0x" + Long.toHexString(start));
        Set<Long> seen = new HashSet<>();
        List<Long> level = new ArrayList<>();
        level.add(start); seen.add(start);
        for (int d = 0; d < maxDepth && !level.isEmpty(); d++) {
            List<Long> next = new ArrayList<>();
            for (long a : level) {
                Function f = getFunctionAt(toAddr(a));
                if (f == null) continue;
                Reference[] refs = getReferencesTo(f.getEntryPoint());
                if (refs == null || refs.length == 0) {
                    println(String.format("   d%d 0x%x %s  *** ROOT ***", d, a, f.getName()));
                    continue;
                }
                for (Reference r : refs) {
                    Function c = getFunctionContaining(r.getFromAddress());
                    if (c == null) continue;
                    long ce = c.getEntryPoint().getOffset();
                    println(String.format("   d%d: 0x%x %s  <- called by 0x%x %s @0x%x",
                        d, a, f.getName(), ce, c.getName(), r.getFromAddress().getOffset()));
                    if (seen.add(ce)) next.add(ce);
                }
            }
            level = next;
        }
    }

    public void run() throws Exception {
        roots();
        up(0x1a3b8L, 7);
        up(0xbc20L, 7);
        up(0xf7a0L, 7);
        up(0xdbe0L, 7);
    }
}
