// Tos.java -- recon of PSP_FW_TRUSTED_OS: roots, SVC map, the TA-manifest parsers.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.scalar.Scalar;
import java.util.*;

public class Tos extends GhidraScript {
    DecompInterface di;

    void roots() {
        FunctionManager fm = currentProgram.getFunctionManager();
        println("---- functions with NO callers (candidate entries / SVC handlers)");
        for (Function f : fm.getFunctions(true)) {
            Reference[] refs = getReferencesTo(f.getEntryPoint());
            if (refs == null || refs.length == 0)
                println(String.format("  ROOT 0x%x %s size=0x%x", f.getEntryPoint().getOffset(),
                    f.getName(), f.getBody().getNumAddresses()));
        }
    }

    void svcMap() throws Exception {
        Map<Long, TreeSet<Long>> bySvc = new TreeMap<>();
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        while (it.hasNext()) {
            Instruction in = it.next();
            String m = in.getMnemonicString().toLowerCase();
            if (!m.startsWith("svc") && !m.startsWith("swi")) continue;
            long imm = -1;
            for (int i = 0; i < in.getNumOperands(); i++)
                for (Object o : in.getOpObjects(i)) if (o instanceof Scalar) imm = ((Scalar) o).getUnsignedValue();
            if (imm < 0) continue;
            Function f = getFunctionContaining(in.getAddress());
            bySvc.computeIfAbsent(imm, k -> new TreeSet<>())
                 .add(f == null ? -1 : f.getEntryPoint().getOffset());
        }
        println("---- SVC -> functions");
        for (Map.Entry<Long, TreeSet<Long>> e : bySvc.entrySet()) {
            StringBuilder sb = new StringBuilder();
            for (long f : e.getValue()) sb.append(String.format("0x%x ", f));
            println(String.format("svc 0x%02x (%d): %s", e.getKey(), e.getValue().size(), sb.toString().trim()));
        }
    }

    void callers(long a) {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        println("---- callers of " + f.getName() + " (0x" + Long.toHexString(a) + ")");
        int n = 0;
        for (Reference r : getReferencesTo(f.getEntryPoint())) {
            Function c = getFunctionContaining(r.getFromAddress());
            println("   " + (c == null ? "-" : c.getName()) + " @0x"
                + Long.toHexString(r.getFromAddress().getOffset()));
            n++;
        }
        if (n == 0) println("   (none)");
    }

    void dec(long a) throws Exception {
        Function f = getFunctionAt(toAddr(a));
        if (f == null) { println("no FUN 0x" + Long.toHexString(a)); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(a) + " size=0x"
            + Long.toHexString(f.getBody().getNumAddresses()));
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("   (fail)");
    }

    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        roots();
        svcMap();
        callers(0x146c4L);
        callers(0x14748L);
        callers(0x1480cL);
        dec(0x146c4L);
        dec(0x14748L);
        dec(0x1480cL);
    }
}
