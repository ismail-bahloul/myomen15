// Svcs.java -- per-function SVC (TOS call) immediates. Host-memory mapping shows up
// as the same SVC numbers the validators use; a handler using them without a
// validator is the candidate.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import java.util.*;

public class Svcs extends GhidraScript {
    long svcImm(Instruction in) {
        for (int i = 0; i < in.getNumOperands(); i++)
            for (Object o : in.getOpObjects(i))
                if (o instanceof Scalar) return ((Scalar) o).getUnsignedValue();
        return -1;
    }
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        Map<Long, TreeSet<Long>> bySvc = new TreeMap<>();
        Map<Long, TreeSet<Long>> byFunc = new TreeMap<>();
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        int n = 0;
        while (it.hasNext()) {
            Instruction in = it.next();
            String m = in.getMnemonicString().toLowerCase();
            if (!m.startsWith("svc") && !m.startsWith("swi")) continue;
            long imm = svcImm(in);
            if (imm < 0) continue;
            Function f = getFunctionContaining(in.getAddress());
            long fe = f == null ? -1 : f.getEntryPoint().getOffset();
            bySvc.computeIfAbsent(imm, k -> new TreeSet<>()).add(fe);
            byFunc.computeIfAbsent(fe, k -> new TreeSet<>()).add(imm);
            n++;
        }
        println("svc sites = " + n);
        println("---- SVC number -> functions using it");
        for (Map.Entry<Long, TreeSet<Long>> e : bySvc.entrySet()) {
            StringBuilder sb = new StringBuilder();
            for (long f : e.getValue()) sb.append(String.format("0x%x ", f));
            println(String.format("svc 0x%02x  (%d funcs): %s", e.getKey(), e.getValue().size(), sb.toString().trim()));
        }
        println("---- per-function SVC sets (functions with >= 1 svc)");
        for (Map.Entry<Long, TreeSet<Long>> e : byFunc.entrySet()) {
            StringBuilder sb = new StringBuilder();
            for (long s : e.getValue()) sb.append(String.format("0x%02x ", s));
            println(String.format("  FUN 0x%x : %s", e.getKey(), sb.toString().trim()));
        }
    }
}
