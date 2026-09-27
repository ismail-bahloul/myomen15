// Coverage.java -- is there undisassembled code that could hide the referencer?
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;

public class Coverage extends GhidraScript {
    public void run() throws Exception {
        MemoryBlock b = currentProgram.getMemory().getBlocks()[0];
        Address a = b.getStart(), end = b.getEnd();
        Listing lst = currentProgram.getListing();
        long code = 0, data = 0, undef = 0;
        Address runStart = null; long runLen = 0, bestStart = -1, bestLen = 0;
        Address p = a;
        while (p.compareTo(end) <= 0) {
            Instruction in = lst.getInstructionAt(p);
            if (in != null) { code += in.getLength(); p = p.add(in.getLength()); runStart = null; continue; }
            Data d = lst.getDefinedDataAt(p);
            if (d != null) { data += 1; if (d.getLength() > 1) p = p.add(d.getLength() - 1); p = p.add(1); runStart = null; continue; }
            undef++;
            if (runStart == null) { runStart = p; runLen = 0; }
            runLen++;
            if (runLen > bestLen) { bestLen = runLen; bestStart = runStart.getOffset(); }
            p = p.add(1);
        }
        println(String.format("block 0x%x..0x%x  code=%d data=%d undefined=%d",
            a.getOffset(), end.getOffset(), code, data, undef));
        println(String.format("largest undefined run: %d bytes @0x%x", bestLen, bestStart));
    }
}
