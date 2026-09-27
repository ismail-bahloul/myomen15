// ForceDisas.java -- force Thumb disassembly of the undisassembled code near the
// orphaned strings, then look for any operand pointing into the string region.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import java.math.BigInteger;

public class ForceDisas extends GhidraScript {
    boolean inRegion(long v) {
        return (v >= 0x1800 && v < 0x2700);
    }
    long scan(long from, long to, String tag) {
        long hits = 0;
        Register tm = currentProgram.getRegister("TMode");
        Address a = toAddr(from);
        while (a.getOffset() < to) {
            Instruction in = getInstructionAt(a);
            if (in == null) {
                try { currentProgram.getProgramContext().setValue(tm, a, a, BigInteger.ONE); }
                catch (Exception e) { }
                disassemble(a);
                in = getInstructionAt(a);
            }
            if (in == null) { a = a.add(2); continue; }
            for (int op = 0; op < in.getNumOperands(); op++)
                for (Object o : in.getOpObjects(op))
                    if (o instanceof Scalar) {
                        long v = ((Scalar) o).getUnsignedValue();
                        if (inRegion(v)) {
                            Function f = getFunctionContaining(in.getAddress());
                            println(String.format("[%s] imm=0x%x  %-28s in %s @0x%x", tag, v,
                                in.toString(), f == null ? "-" : f.getName(),
                                in.getAddress().getOffset()));
                            hits++;
                        }
                    }
            a = a.add(in.getLength());
        }
        return hits;
    }
    public void run() throws Exception {
        long n = 0;
        n += scan(0x1553L, 0x18dcL, "pre-0x18dc");
        n += scan(0x1f57L, 0x2600L, "1f57-2600");
        n += scan(0x4ad9L, 0x4e01L, "smu-fw");
        n += scan(0x5489L, 0x5700L, "dirsearch");
        println("total region hits = " + n);
    }
}
