import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import java.util.*;

public class Up extends GhidraScript {
    public void run() throws Exception {
        long start = 0x2bacL;
        Map<Long,Long> parent = new HashMap<>();
        Deque<Long> q = new ArrayDeque<>(); q.add(start);
        Set<Long> seen = new HashSet<>(); seen.add(start);
        int depth = 0;
        long[] level = new long[]{start};
        while (depth < 4 && level.length > 0) {
            List<Long> next = new ArrayList<>();
            for (long a : level) {
                Function f = getFunctionAt(toAddr(a));
                if (f == null) continue;
                for (Reference r : getReferencesTo(f.getEntryPoint())) {
                    Address from = r.getFromAddress();
                    Function c = getFunctionContaining(from);
                    if (c != null && !seen.contains(c.getEntryPoint().getOffset())) {
                        long ce = c.getEntryPoint().getOffset();
                        seen.add(ce); parent.put(ce, a); next.add(ce);
                        println(String.format("depth %d: 0x%x %s  <- called by 0x%x %s",
                            depth+1, ce, c.getName(), a, f.getName()));
                    }
                }
            }
            level = next.stream().mapToLong(Long::longValue).toArray();
            depth++;
        }
        println("total ancestors found: " + seen.size());
    }
}
