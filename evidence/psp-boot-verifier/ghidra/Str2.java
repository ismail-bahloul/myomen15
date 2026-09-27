// Str2.java -- map the TOS and locate the code that references TA/GP strings.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;

public class Str2 extends GhidraScript {
    void xref(String needle) throws Exception {
        byte[] pat = needle.getBytes("US-ASCII");
        Memory mem = currentProgram.getMemory();
        Address a = mem.getMinAddress();
        byte[] buf = new byte[(int) mem.getSize()];
        mem.getBytes(a, buf);
        int hits = 0;
        for (int i = 0; i + pat.length < buf.length; i++) {
            boolean ok = true;
            for (int j = 0; j < pat.length; j++) if (buf[i + j] != pat[j]) { ok = false; break; }
            if (!ok) continue;
            Address found = toAddr(i);
            hits++;
            Reference[] refs = getReferencesTo(found);
            println(String.format("%-34s @0x%x   refs=%d", needle, (long) i,
                refs == null ? 0 : refs.length));
            if (refs != null) for (Reference r : refs) {
                Function f = getFunctionContaining(r.getFromAddress());
                println(String.format("      from 0x%x  in %s  (%s)",
                    r.getFromAddress().getOffset(), f == null ? "-" : f.getName(), r.getReferenceType()));
            }
        }
        if (hits == 0) println("NOT FOUND: " + needle);
    }
    public void run() throws Exception {
        println("lang = " + currentProgram.getLanguageID());
        for (MemoryBlock b : currentProgram.getMemory().getBlocks())
            println("block " + b.getName() + " 0x" + Long.toHexString(b.getStart().getOffset())
                + " size=0x" + Long.toHexString(b.getSize()) + " X=" + b.isExecute());
        FunctionManager fm = currentProgram.getFunctionManager();
        int n = 0;
        for (Function f : fm.getFunctions(true)) n++;
        println("functions = " + n);
        xref("$PS1");
        xref("gpd.ta.appID");
        xref("gpd.ta.heapSize");
        xref("amd.ta.SecHeapSize");
        xref("amd.dr.driverID");
        xref("AMD-TEE Global Platform API");
        xref("gpd.tee.deviceID");
    }
}
