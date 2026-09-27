// AuditBoot.java -- same sweep as Audit.java, but for the boot loader's command
// handler FUN_000073e8. Does each handler reach a boot-family validator?
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.util.*;

public class AuditBoot extends GhidraScript {
    static final long[] INTERESTING = {
        0x738cL, 0x148cL, 0xdea0L, 0xb8acL, 0xe108L, 0x3eb8L, 0x147eL
    };
    static final String[] NAMES = {
        "range(738c)", "region(148c)", "boundedCopy(dea0)", "verify(b8ac)",
        "spiRead(e108)", "GetHdr(3eb8)", "147e"
    };

    boolean reach(Function start, int depth, Map<Long,Integer> hits) {
        Set<Long> seen = new HashSet<>();
        Deque<Object[]> q = new ArrayDeque<>();
        q.add(new Object[]{start, 0}); seen.add(start.getEntryPoint().getOffset());
        boolean any = false;
        while (!q.isEmpty()) {
            Object[] cur = q.poll();
            Function f = (Function) cur[0];
            int d = (Integer) cur[1];
            if (d >= depth) continue;
            for (Function c : f.getCalledFunctions(monitor)) {
                long ce = c.getEntryPoint().getOffset();
                for (int i = 0; i < INTERESTING.length; i++)
                    if (INTERESTING[i] == ce) { hits.put(ce, d + 1); any = true; }
                if (seen.add(ce)) q.add(new Object[]{c, d + 1});
            }
        }
        return any;
    }

    public void run() throws Exception {
        Function disp = getFunctionAt(toAddr(0x73e8L));
        if (disp == null) { println("no dispatcher"); return; }
        println("dispatcher FUN_000073e8 size=0x"
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
                sb.append(nm).append(" ");
            }
            boolean hasVal = hits.containsKey(0x738cL) || hits.containsKey(0x148cL)
                || hits.containsKey(0xdea0L) || hits.containsKey(0xb8acL);
            println(String.format("%s 0x%x size=0x%x  ->  %s",
                hasVal ? "  VAL" : "NOVAL", h.getEntryPoint().getOffset(),
                h.getBody().getNumAddresses(), sb.toString().trim()));
            if (!hasVal) noVal.add(h);
        }
        println("---- handlers with NO boot validator reachable: " + noVal.size());
        for (Function h : noVal)
            println(String.format("   0x%x %s size=0x%x", h.getEntryPoint().getOffset(),
                h.getName(), h.getBody().getNumAddresses()));
    }
}
