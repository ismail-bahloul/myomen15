// ForceFunc.java -- recreate and decompile the undisassembled functions that
// reference the "orphaned" strings (log_validate_bios_l2_directory, HVB validation).
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;
import java.math.BigInteger;

public class ForceFunc extends GhidraScript {
    Register tm;
    Memory mem;
    DecompInterface di;

    long findPushBefore(long adr) throws Exception {
        for (long a = adr; a > adr - 0x400; a -= 2) {
            int h = mem.getShort(toAddr(a)) & 0xffff;
            if ((h & 0xFE00) == 0xB400 || h == 0xE92D) return a;
        }
        return -1;
    }

    void build(long start, long end) throws Exception {
        Address a = toAddr(start);
        while (a.getOffset() < end) {
            if (getInstructionAt(a) == null) {
                try { currentProgram.getProgramContext().setValue(tm, a, a, BigInteger.ONE); }
                catch (Exception e) { }
                disassemble(a);
            }
            Instruction in = getInstructionAt(a);
            if (in == null) { a = a.add(2); continue; }
            a = a.add(in.getLength());
        }
    }

    void show(long adr) throws Exception {
        long start = findPushBefore(adr);
        println("---- ADR @0x" + Long.toHexString(adr) + " -> function start 0x"
            + (start < 0 ? "?" : Long.toHexString(start)));
        if (start < 0) return;
        build(start, adr + 0x200);
        Function f = getFunctionAt(toAddr(start));
        if (f == null) {
            try { f = createFunction(toAddr(start), "FUN_boot_" + Long.toHexString(start)); }
            catch (Exception e) { println("createFunction: " + e); }
        }
        if (f == null) { println("(could not create function)"); return; }
        DecompileResults res = di.decompileFunction(f, 120, monitor);
        if (res != null && res.getDecompiledFunction() != null)
            println(res.getDecompiledFunction().getC());
        else println("(decompile failed)");
    }

    public void run() throws Exception {
        tm = currentProgram.getRegister("TMode");
        mem = currentProgram.getMemory();
        di = new DecompInterface();
        di.openProgram(currentProgram);
        show(0x1726L);   // references load_validate_bios_l2_directory
        show(0x256eL);   // references "Detected 2nd level entry for HVB validation"
    }
}
