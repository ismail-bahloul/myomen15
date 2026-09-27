// Audit.java -- for every handler called by the DRIVER_ENTRIES command dispatcher,
// does it reach a host-buffer validator / the entry verifier? Handlers that do NOT
// are the candidates for an unvalidated host path.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import java.util.*;

public class Audit extends GhidraScript {
    static final long[] INTERESTING = {
        0x11604L, 0x7730L, 0xc4bcL, 0xf7a0L, 0x138fcL, 0x13570L, 0x5748L, 0x553cL
    };
    static final String[] NAMES = {
        "validate(11604)", "map(7730)", "c4bc", "entryVerify(f7a0)",
        "rsa-op(138fc)", "pkcs1(13570)", "map2(5748)", "0x553c"
    };

    Set<Long> reach(Function start, int depth, Map<Long,Integer> hitDepth) {
        Set<Long> seen = new HashSet<>();
        Deque<Object[]> q = new ArrayDeque<>();
        q.add(new Object[]{start, 0});
        seen.add(start.getEntryPoint().getOffset());
        while (!q.isEmpty()) {
            Object[] cur = q.poll();
            Function f = (Function) cur[0];
            int d = (Integer) cur[1];
            if (d >= depth) continue;
            for (Function c : f.getCalledFunctions(monitor)) {
                long ce = c.getEntryPoint().getOffset();
                for (int i = 0; i < INTERESTING.length; i++)
                    if (INTERESTING[i] == ce && !hitDepth.containsKey(ce)) hitDepth.put(ce, d + 1);
                if (seen.add(ce)) q.add(new Object[]{c, d + 1});
            }
        }
        return seen;
    }

    public void run() throws Exception {
        Function disp = getFunctionAt(toAddr(0xdbe0L));
        if (disp == null) { println("no dispatcher"); return; }
        println("dispatcher FUN_0000dbe0 size=0x"
            + Long.toHexString(disp.getBody().getNumAddresses()));
        Set<Function> handlers = disp.getCalledFunctions(monitor);
        println("handlers called directly = " + handlers.size());
        List<Function> noVal = new ArrayList<>();
        for (Function h : handlers) {
            Map<Long,Integer> hits = new TreeMap<>();
            reach(h, 4, hits);
            StringBuilder sb = new StringBuilder();
            for (Map.Entry<Long,Integer> e : hits.entrySet()) {
                String nm = String.format("0x%x", e.getKey());
                for (int i = 0; i < INTERESTING.length; i++)
                    if (INTERESTING[i] == e.getKey()) nm = NAMES[i];
                sb.append(nm).append("@d").append(e.getValue()).append(" ");
            }
            boolean hasVal = hits.containsKey(0x11604L) || hits.containsKey(0x7730L)
                || hits.containsKey(0xc4bcL);
            println(String.format("%s 0x%x size=0x%x  ->  %s",
                hasVal ? "  VAL" : "NOVAL", h.getEntryPoint().getOffset(),
                h.getBody().getNumAddresses(), sb.toString().trim()));
            if (!hasVal) noVal.add(h);
        }
        println("---- handlers with NO validator reachable (candidates): " + noVal.size());
        for (Function h : noVal)
            println(String.format("   0x%x %s size=0x%x", h.getEntryPoint().getOffset(),
                h.getName(), h.getBody().getNumAddresses()));
    }
}
