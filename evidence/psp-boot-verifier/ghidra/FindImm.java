// FindImm.java -- what code builds the addresses of the unresolved strings?
// Scan every instruction operand for an immediate equal to a target address (or its
// low/high 16 bits, i.e. a movw/movt half), and report the containing function.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;

public class FindImm extends GhidraScript {
    static final long[] T = { 0x19c8L, 0x25a8L, 0x18dcL, 0x1900L, 0x3f30L, 0x5434L, 0x2af8L };
    static final String[] N = {
        "load_validate_bios_l2_directory", "HVB validation", "Bootloader C entry",
        "load_bios_l1_directory", "GetPspFwHeader(ref ok)", "PSPDirectorySearch", "CryptoModExp"
    };
    public void run() throws Exception {
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        long n = 0;
        while (it.hasNext()) {
            Instruction in = it.next();
            n++;
            for (int op = 0; op < in.getNumOperands(); op++) {
                for (Object o : in.getOpObjects(op)) {
                    if (!(o instanceof Scalar)) continue;
                    long v = ((Scalar) o).getUnsignedValue();
                    for (int i = 0; i < T.length; i++) {
                        long t = T[i];
                        if (v == t || v == (t & 0xffff) || v == (t >>> 16)) {
                            Function f = getFunctionContaining(in.getAddress());
                            println(String.format("%-32s imm=0x%x  %s  in %s @0x%x",
                                N[i], v, in.toString(), f == null ? "-" : f.getName(),
                                in.getAddress().getOffset()));
                        }
                    }
                }
            }
        }
        println("scanned instructions = " + n);
    }
}
