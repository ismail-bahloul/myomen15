// Disasm.java -- linear disassembly of a function body, flagging indirect control flow.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;

public class Disasm extends GhidraScript {
    void dis(long start, long end) throws Exception {
        Listing lst = currentProgram.getListing();
        Memory mem = currentProgram.getMemory();
        Address a = toAddr(start);
        while (a.getOffset() < end) {
            Instruction in = lst.getInstructionAt(a);
            if (in == null) {
                byte b = mem.getByte(a);
                println(String.format("0x%x  .byte 0x%02x", a.getOffset(), b & 0xff));
                a = a.add(1);
                continue;
            }
            String m = in.getMnemonicString().toLowerCase();
            String flag = "";
            if (m.equals("tbb") || m.equals("tbh") || m.startsWith("bx") || m.startsWith("blx")
                || (m.startsWith("ldr") && in.toString().contains("pc"))
                || (m.startsWith("add") && in.toString().contains("pc")
                    && !in.toString().contains("#")))
                flag = "   <<< INDIRECT";
            println(String.format("0x%x  %-40s%s", a.getOffset(),
                in.toString().replace("\n", " "), flag));
            a = a.add(in.getLength());
        }
    }
    public void run() throws Exception {
        Function f = getFunctionAt(toAddr(0x16748L));
        if (f == null) { println("no FUN 0x16748"); return; }
        println("function " + f.getName() + " body " + f.getBody());
        dis(0x16748L, 0x16fb8L);
    }
}
