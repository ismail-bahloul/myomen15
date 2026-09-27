// Undef.java -- list undefined (undisassembled, undefined-data) runs and sample them.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;

public class Undef extends GhidraScript {
    public void run() throws Exception {
        MemoryBlock b = currentProgram.getMemory().getBlocks()[0];
        Memory mem = currentProgram.getMemory();
        Listing lst = currentProgram.getListing();
        Address p = b.getStart(), end = b.getEnd();
        Address runStart = null; long runLen = 0;
        int shown = 0;
        while (p.compareTo(end) <= 0) {
            boolean isUndef = lst.getInstructionAt(p) == null && lst.getDefinedDataAt(p) == null;
            if (isUndef) {
                if (runStart == null) { runStart = p; runLen = 0; }
                runLen++;
            } else {
                if (runLen >= 64) { dump(mem, runStart, runLen); if (++shown > 40) { println("..."); return; } }
                runStart = null; runLen = 0;
            }
            p = p.add(1);
        }
        if (runLen >= 64) dump(mem, runStart, runLen);
    }
    void dump(Memory mem, Address start, long len) throws Exception {
        byte[] buf = new byte[24];
        int n = (int) Math.min(24, len);
        mem.getBytes(start, buf, 0, n);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) sb.append(String.format("%02x", buf[i] & 0xff));
        println(String.format("undef %6d B @0x%-6x  %s", len, start.getOffset(), sb.toString()));
    }
}
