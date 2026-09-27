// RegionRefs.java -- everything that points into the boot loader's early string region.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;

public class RegionRefs extends GhidraScript {
    boolean inRegion(long v) {
        return (v >= 0x1800 && v < 0x2700) || (v >= 0x5400 && v < 0x5600);
    }
    public void run() throws Exception {
        println("---- operand values in the string region ----");
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        int n = 0;
        while (it.hasNext()) {
            Instruction in = it.next();
            for (int op = 0; op < in.getNumOperands(); op++) {
                for (Object o : in.getOpObjects(op)) {
                    if (!(o instanceof Scalar)) continue;
                    long v = ((Scalar) o).getUnsignedValue();
                    if (inRegion(v)) {
                        Function f = getFunctionContaining(in.getAddress());
                        println(String.format("imm=0x%x  %-30s in %s @0x%x", v, in.toString(),
                            f == null ? "-" : f.getName(), in.getAddress().getOffset()));
                        n++;
                    }
                }
            }
        }
        println("total = " + n);
        println("---- which of the early strings are defined data with refs ----");
        for (long a : new long[]{0x18dcL, 0x1900L, 0x1930L, 0x1968L, 0x1998L, 0x19c8L, 0x1a04L,
                                 0x1a38L, 0x1a50L, 0x1ff4L, 0x25a8L, 0x5434L, 0x2af8L}) {
            Data d = getDataAt(toAddr(a));
            var refs = getReferencesTo(toAddr(a));
            println(String.format("0x%x  data=%s  refs=%d", a,
                d == null ? "none" : (d.hasStringValue() ? "str" : d.getDataType().getName()),
                refs == null ? 0 : refs.length));
        }
    }
}
