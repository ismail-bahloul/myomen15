import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;

public class StrXref extends GhidraScript {
    void xref(String needle) throws Exception {
        // find the string in memory
        byte[] pat = needle.getBytes("US-ASCII");
        Address found = null;
        Memory mem = currentProgram.getMemory();
        Address a = mem.getMinAddress();
        byte[] buf = new byte[(int)mem.getSize()];
        mem.getBytes(a, buf);
        for (int i = 0; i + pat.length < buf.length; i++) {
            boolean ok = true;
            for (int j = 0; j < pat.length; j++) if (buf[i+j] != pat[j]) { ok = false; break; }
            if (ok) { found = toAddr(i); break; }
        }
        if (found == null) { println("NOT FOUND: " + needle); return; }
        println(String.format("%-40s @0x%x", needle, found.getOffset()));
        Reference[] refs = getReferencesTo(found);
        if (refs == null || refs.length == 0) { println("   (no refs)"); return; }
        for (Reference r : refs) {
            Address from = r.getFromAddress();
            Function f = getFunctionContaining(from);
            println(String.format("   ref from 0x%x  in %s  (%s)",
                from.getOffset(), f==null?"-":f.getName(), r.getReferenceType()));
        }
    }
    public void run() throws Exception {
        xref("load_validate_bios_l2_directory");
        xref("Detected 2nd level entry for HVB validation");
        xref("PSPDirectorySearch()::Enter-EntryType");
        xref("CryptoModExp Invalid Parameter");
        xref("RPMC signature validation failed");
        xref("Bootloader C entry start");
        xref("ReadAndCopyRTMSignature");
    }
}
