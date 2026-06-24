//@category Data Types
//@author gdt2r2sdb

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.data.Array;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.DataTypeComponent;
import ghidra.program.model.data.DefaultDataType;
import ghidra.program.model.data.Enum;
import ghidra.program.model.data.FileDataTypeManager;
import ghidra.program.model.data.FunctionDefinition;
import ghidra.program.model.data.ParameterDefinition;
import ghidra.program.model.data.Pointer;
import ghidra.program.model.data.Structure;
import ghidra.program.model.data.TypeDef;
import ghidra.program.model.data.Union;
import ghidra.program.model.data.VoidDataType;

public class GdtToR2SdbText extends GhidraScript {
    private PrintWriter out;
    private int pointerBits = 64;
    private String defaultCc = "";

    private final Set<String> emittedTop = new HashSet<String>();
    private final Set<String> emittedFuncs = new HashSet<String>();
    private final Set<String> emittedPointerTypes = new HashSet<String>();
    private final IdentityHashMap<DataType, String> anonNames = new IdentityHashMap<DataType, String>();
    private int anonId = 0;
    private int recordCount = 0;

    @Override
    public void run() throws Exception {
        String[] argv = getScriptArgs();
        if (argv.length < 2) {
            printerr("usage: GdtToR2SdbText <input.gdt> <out.sdb.txt> [pointer-bits=64] [default-callconv]");
            return;
        }

        File gdt = new File(argv[0]).getAbsoluteFile();
        File outFile = new File(argv[1]).getAbsoluteFile();
        if (argv.length >= 3) {
            pointerBits = Integer.parseInt(argv[2]);
        }
        if (argv.length >= 4) {
            defaultCc = argv[3];
        }

        File parent = outFile.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }

        println("[GdtToR2SdbText] gdt=" + gdt);
        println("[GdtToR2SdbText] out=" + outFile);
        println("[GdtToR2SdbText] pointerBits=" + pointerBits);

        FileDataTypeManager dtm = FileDataTypeManager.openFileArchive(gdt, false);
        try {
            out = new PrintWriter(new BufferedWriter(new FileWriter(outFile)));
            emitPrimitivePrelude();

            List<DataType> dts = new ArrayList<DataType>();
            Iterator<DataType> it = dtm.getAllDataTypes();
            while (it.hasNext()) {
                dts.add(it.next());
            }
            Collections.sort(dts, (a, b) -> stableName(a).compareTo(stableName(b)));

            for (DataType dt : dts) {
                emitDataType(dt);
            }

            out.flush();
            println("[GdtToR2SdbText] wrote records=" + recordCount);
        }
        finally {
            if (out != null) {
                out.close();
            }
            dtm.close();
        }
    }

    private void kv(String key, String value) {
        if (key == null || key.length() == 0) {
            return;
        }
        if (value == null) {
            value = "";
        }
        key = key.replace('\n', '_').replace('\r', '_').trim();
        value = value.replace('\n', ' ').replace('\r', ' ').trim();
        out.println(key + "=" + value);
        recordCount++;
    }

    private void emitPrimitivePrelude() {
        primitive("void", "v", 0);
        primitive("bool", "b", 8);
        primitive("char", "c", 8);
        primitive("int8_t", "c", 8);
        primitive("uint8_t", "b", 8);
        primitive("int16_t", "w", 16);
        primitive("uint16_t", "w", 16);
        primitive("int32_t", "d", 32);
        primitive("uint32_t", "d", 32);
        primitive("int64_t", "q", 64);
        primitive("uint64_t", "q", 64);
        primitive("intptr_t", pointerBits == 32 ? "d" : "q", pointerBits);
        primitive("uintptr_t", pointerBits == 32 ? "d" : "q", pointerBits);
        primitive("size_t", pointerBits == 32 ? "d" : "q", pointerBits);
        primitive("float", "f", 32);
        primitive("double", "F", 64);
        emitPointerType("void *", "void");
        emitPointerType("char *", "char");
    }

    private void primitive(String name, String pf, int bits) {
        kv(name, "type");
        kv("type." + name, pf);
        kv("type." + name + ".size", Integer.toString(bits));
    }

    private void emitDataType(DataType dt) {
        if (dt == null || dt instanceof DefaultDataType || dt instanceof VoidDataType) {
            return;
        }
        dt = unwrapArray(dt).base;

        if (isPrimitive(dt)) {
            return;
        }
        if (dt instanceof Pointer) {
            Pointer p = (Pointer) dt;
            emitPointerType(r2Type(dt), r2Type(p.getDataType()));
            emitDataType(p.getDataType());
            return;
        }
        if (dt instanceof TypeDef) {
            emitTypedef((TypeDef) dt);
            return;
        }
        if (dt instanceof Structure) {
            if (!isAnonymousAggregate(dt)) {
                emitStruct((Structure) dt);
            }
            return;
        }
        if (dt instanceof Union) {
            if (!isAnonymousAggregate(dt)) {
                emitUnion((Union) dt);
            }
            return;
        }
        if (dt instanceof Enum) {
            emitEnum((Enum) dt);
            return;
        }
        if (dt instanceof FunctionDefinition) {
            emitFunction((FunctionDefinition) dt, stableName(dt));
        }
    }

    private void emitPointerType(String ptrName, String pointTo) {
        ptrName = ptrName.trim();
        if (ptrName.length() == 0 || !emittedPointerTypes.add(ptrName)) {
            return;
        }
        kv(ptrName, "type");
        kv("type." + ptrName, "p");
        kv("type." + ptrName + ".size", Integer.toString(pointerBits));
        if (pointTo != null && pointTo.length() > 0) {
            kv("type." + ptrName + ".pointto", pointTo);
        }
    }

    private void emitTypedef(TypeDef td) {
        String name = stableName(td);
        if (!emittedTop.add(name)) {
            return;
        }

        DataType base = td.getBaseDataType();
        DataType arrBase = unwrapArray(base).base;
        if (arrBase instanceof FunctionDefinition) {
            emitFunction((FunctionDefinition) arrBase, name);
            kv(name, "typedef");
            kv("typedef." + name, "func." + name);
            return;
        }
        if (base instanceof Pointer) {
            Pointer p = (Pointer) base;
            DataType pt = p.getDataType();
            if (pt instanceof FunctionDefinition) {
                emitFunction((FunctionDefinition) pt, name);
                kv(name, "typedef");
                kv("typedef." + name, "func." + name);
                return;
            }
        }

        emitDataType(base);
        kv(name, "typedef");
        kv("typedef." + name, r2Type(base));
    }

    private void emitStruct(Structure s) {
        String name = stableName(s);
        if (!emittedTop.add(name)) {
            return;
        }
        kv(name, "struct");

        List<String> fields = new ArrayList<String>();
        Map<String, Integer> seen = new HashMap<String, Integer>();
        for (DataTypeComponent c : s.getDefinedComponents()) {
            appendComponent("struct", name, fields, seen, c, c.getOffset());
        }
        kv("struct." + name, join(fields));
    }

    private void emitUnion(Union u) {
        String name = stableName(u);
        if (!emittedTop.add(name)) {
            return;
        }
        kv(name, "union");

        List<String> fields = new ArrayList<String>();
        Map<String, Integer> seen = new HashMap<String, Integer>();
        for (DataTypeComponent c : u.getComponents()) {
            appendComponent("union", name, fields, seen, c, 0);
        }
        kv("union." + name, join(fields));
    }

    private void appendComponent(String ownerKind, String ownerName, List<String> fields,
            Map<String, Integer> seen, DataTypeComponent c, int absoluteOffset) {
        DataType raw = c.getDataType();
        ArrayInfo ai = unwrapArray(raw);
        DataType base = ai.base;

        if (isAnonymousAggregateComponent(c, base)) {
            if (base instanceof Structure) {
                Structure nested = (Structure) base;
                for (DataTypeComponent nc : nested.getDefinedComponents()) {
                    appendComponent(ownerKind, ownerName, fields, seen, nc, absoluteOffset + nc.getOffset());
                }
                return;
            }
            if (base instanceof Union) {
                Union nested = (Union) base;
                for (DataTypeComponent nc : nested.getComponents()) {
                    appendComponent(ownerKind, ownerName, fields, seen, nc, absoluteOffset);
                }
                return;
            }
        }

        emitDataType(base);
        String fname = componentName(c, "field_" + absoluteOffset);
        fname = uniqueFieldName(cleanName(fname), seen);
        fields.add(fname);
        kv(ownerKind + "." + ownerName + "." + fname,
            r2Type(base) + "," + absoluteOffset + "," + ai.count);
        kv(ownerKind + "." + ownerName + "." + fname + ".meta",
            ai.count > 0 ? Integer.toString(ai.elementBytes) : "0");
    }

    private boolean isAnonymousAggregateComponent(DataTypeComponent c, DataType base) {
        if (!(base instanceof Structure || base instanceof Union)) {
            return false;
        }

        // Ghidra sometimes gives anonymous union/struct components synthetic names
        // like field7_0x38 instead of leaving getFieldName() empty.  If we do not
        // treat those as anonymous aggregates, IL2CPP MethodInfo-style anonymous
        // unions export as field7_0x38/field8_0x40 instead of their real members:
        // rgctx_data, methodMetadataHandle, genericMethod, genericContainerHandle.
        String explicit = c.getFieldName();
        String def = c.getDefaultFieldName();
        if (explicit == null || explicit.trim().length() == 0) {
            return true;
        }
        if (isSyntheticComponentName(explicit)) {
            return true;
        }
        if (isSyntheticComponentName(def) && explicit.equals(def)) {
            return true;
        }
        return isAnonymousAggregate(base);
    }

    private boolean isAnonymousAggregate(DataType dt) {
        if (!(dt instanceof Structure || dt instanceof Union)) {
            return false;
        }
        String n = dt.getName();
        if (n == null) {
            return true;
        }
        String k = n.trim().toLowerCase();
        return k.length() == 0 || k.startsWith("anon") || k.startsWith("<anonymous") ||
            k.indexOf("anonymous") >= 0 || k.indexOf("unnamed") >= 0 ||
            isSyntheticComponentName(k) || k.matches("(struct|union)_?\\d+.*");
    }

    private boolean isSyntheticComponentName(String name) {
        if (name == null) {
            return false;
        }
        String k = name.trim().toLowerCase();
        return k.matches("field\\d+(_0x[0-9a-f]+)?") ||
            k.matches("field_\\d+(_0x[0-9a-f]+)?") ||
            k.matches("anon_?(struct|union)?_?\\d+.*") ||
            k.matches("(struct|union)_?\\d+.*");
    }

    private void emitEnum(Enum e) {
        String name = stableName(e);
        if (!emittedTop.add(name)) {
            return;
        }
        kv(name, "enum");
        List<String> names = new ArrayList<String>();
        for (String rawName : e.getNames()) {
            String caseName = cleanName(rawName);
            names.add(caseName);
            long v = e.getValue(rawName);
            String hx = "0x" + Long.toHexString(v);
            kv("enum." + name + "." + caseName, hx);
            kv("enum." + name + "." + hx, caseName);
        }
        kv("enum." + name, join(names));
    }

    private void emitFunction(FunctionDefinition f, String preferredName) {
        String name = cleanName(preferredName);
        if (name.length() == 0 || name.equals("undefined")) {
            name = stableName(f);
        }
        if (!emittedFuncs.add(name)) {
            return;
        }
        kv(name, "func");
        ParameterDefinition[] args = f.getArguments();
        kv("func." + name + ".args", Integer.toString(args.length));
        for (int i = 0; i < args.length; i++) {
            ParameterDefinition p = args[i];
            String argName = p.getName();
            if (argName == null || argName.trim().length() == 0) {
                argName = "arg" + i;
            }
            emitDataType(p.getDataType());
            kv("func." + name + ".arg" + i, r2Type(p.getDataType()) + "," + cleanName(argName));
        }
        emitDataType(f.getReturnType());
        kv("func." + name + ".ret", r2Type(f.getReturnType()));
        try {
            String cc = f.getCallingConventionName();
            if (cc != null && cc.length() > 0 && !cc.equals("unknown")) {
                kv("func." + name + ".cc", cc);
            }
            else if (defaultCc != null && defaultCc.length() > 0) {
                kv("func." + name + ".cc", defaultCc);
            }
        }
        catch (Throwable t) {
            if (defaultCc != null && defaultCc.length() > 0) {
                kv("func." + name + ".cc", defaultCc);
            }
        }
        try {
            if (f.hasNoReturn()) {
                kv("func." + name + ".noreturn", "true");
            }
        }
        catch (Throwable t) {
            // Older Ghidra versions may not expose this consistently.
        }
    }

    private String r2Type(DataType dt) {
        if (dt == null || dt instanceof DefaultDataType || dt instanceof VoidDataType) {
            return "void";
        }
        ArrayInfo ai = unwrapArray(dt);
        dt = ai.base;

        if (dt instanceof TypeDef) {
            return stableName(dt);
        }
        if (dt instanceof Pointer) {
            Pointer p = (Pointer) dt;
            DataType base = p.getDataType();
            if (base == null || base instanceof DefaultDataType || base instanceof VoidDataType) {
                return "void *";
            }
            return r2Type(base) + " *";
        }
        if (dt instanceof Structure || dt instanceof Union || dt instanceof Enum || dt instanceof FunctionDefinition) {
            return stableName(dt);
        }

        String prim = primitiveName(dt);
        if (prim != null) {
            return prim;
        }
        return stableName(dt);
    }

    private boolean isPrimitive(DataType dt) {
        return primitiveName(dt) != null;
    }

    private String primitiveName(DataType dt) {
        if (dt == null) {
            return "void";
        }
        // Important: do not classify user structures/unions/enums by name.
        // IL2CPP contains real structs such as
        // UnityEngine_UIElements_UnsignedIntegerField_UxmlFactory_Fields.
        // A loose "name contains unsigned" primitive fallback would otherwise
        // drop those structs from the exported SDB.
        if (dt instanceof Structure || dt instanceof Union || dt instanceof Enum || dt instanceof FunctionDefinition) {
            return null;
        }
        String n = dt.getName();
        if (n == null) {
            return null;
        }
        String k = n.trim().toLowerCase();
        int len = dt.getLength();

        if (k.equals("void")) return "void";
        if (k.equals("bool") || k.equals("boolean") || k.equals("_bool")) return "bool";
        if (k.equals("char")) return "char";
        if (k.equals("signed char") || k.equals("sbyte")) return "int8_t";
        if (k.equals("unsigned char") || k.equals("uchar") || k.equals("byte")) return "uint8_t";
        if (k.equals("short") || k.equals("signed short") || k.equals("short int")) return "int16_t";
        if (k.equals("unsigned short") || k.equals("ushort") || k.equals("word")) return "uint16_t";
        if (k.equals("int") || k.equals("signed int") || k.equals("integer")) return "int32_t";
        if (k.equals("unsigned int") || k.equals("uint") || k.equals("dword")) return "uint32_t";
        if (k.equals("long long") || k.equals("signed long long") || k.equals("longlong")) return "int64_t";
        if (k.equals("unsigned long long") || k.equals("ulonglong") || k.equals("qword")) return "uint64_t";
        if (k.equals("long")) return pointerBits == 32 ? "int32_t" : "int64_t";
        if (k.equals("unsigned long") || k.equals("ulong")) return pointerBits == 32 ? "uint32_t" : "uint64_t";
        if (k.equals("float")) return "float";
        if (k.equals("double")) return "double";
        if (k.equals("undefined") || k.equals("default")) return "void";
        if (k.equals("undefined1")) return "uint8_t";
        if (k.equals("undefined2")) return "uint16_t";
        if (k.equals("undefined4")) return "uint32_t";
        if (k.equals("undefined8")) return "uint64_t";
        if (k.equals("size_t")) return "size_t";
        if (k.equals("intptr_t")) return "intptr_t";
        if (k.equals("uintptr_t")) return "uintptr_t";
        if (k.equals("uint8_t") || k.equals("uint16_t") || k.equals("uint32_t") || k.equals("uint64_t")) return cleanName(n);
        if (k.equals("int8_t") || k.equals("int16_t") || k.equals("int32_t") || k.equals("int64_t")) return cleanName(n);

        if (len == 1 && k.indexOf("unsigned") >= 0) return "uint8_t";
        if (len == 1 && k.indexOf("signed") >= 0) return "int8_t";
        if (len == 2 && k.indexOf("unsigned") >= 0) return "uint16_t";
        if (len == 2 && k.indexOf("signed") >= 0) return "int16_t";
        if (len == 4 && k.indexOf("unsigned") >= 0) return "uint32_t";
        if (len == 4 && k.indexOf("signed") >= 0) return "int32_t";
        if (len == 8 && k.indexOf("unsigned") >= 0) return "uint64_t";
        if (len == 8 && k.indexOf("signed") >= 0) return "int64_t";
        return null;
    }

    private static class ArrayInfo {
        DataType base;
        int count;
        int elementBytes;
        ArrayInfo(DataType base, int count, int elementBytes) {
            this.base = base;
            this.count = count;
            this.elementBytes = elementBytes;
        }
    }

    private ArrayInfo unwrapArray(DataType dt) {
        int count = 0;
        int elementBytes = 0;
        while (dt instanceof Array) {
            Array a = (Array) dt;
            int n = a.getNumElements();
            if (n <= 0) {
                n = 1;
            }
            count = count == 0 ? n : count * n;
            elementBytes = a.getElementLength();
            dt = a.getDataType();
        }
        return new ArrayInfo(dt, count, elementBytes);
    }

    private String componentName(DataTypeComponent c, String fallback) {
        String fname = c.getFieldName();
        if (fname == null || fname.trim().length() == 0) {
            fname = c.getDefaultFieldName();
        }
        if (fname == null || fname.trim().length() == 0) {
            fname = fallback;
        }
        return fname;
    }

    private String uniqueFieldName(String base, Map<String, Integer> seen) {
        Integer n = seen.get(base);
        if (n == null) {
            seen.put(base, 1);
            return base;
        }
        seen.put(base, n + 1);
        return base + "_" + n;
    }

    private String stableName(DataType dt) {
        if (dt == null) {
            return "void";
        }
        String prim = primitiveName(dt);
        if (prim != null) {
            return prim;
        }
        String n = dt.getName();
        if (n == null || n.trim().length() == 0 || n.startsWith("anon") || n.startsWith("<anonymous")) {
            String prior = anonNames.get(dt);
            if (prior != null) {
                return prior;
            }
            String generated = "anon_type_" + (++anonId);
            anonNames.put(dt, generated);
            return generated;
        }
        // Preserve the header's declared type name. Do NOT prefix Ghidra category paths.
        return cleanName(n);
    }

    private String cleanName(String s) {
        if (s == null) {
            return "";
        }
        s = s.trim();
        s = s.replaceFirst("^(struct|union|enum)\\s+", "");
        s = s.replace("::", "_");
        s = s.replace('.', '_');
        s = s.replace('/', '_');
        s = s.replace('$', '_');
        // Replace invalid characters only. Do NOT collapse repeated or leading underscores.
        s = s.replaceAll("[^A-Za-z0-9_]", "_");
        if (s.length() == 0) {
            s = "anon";
        }
        if (Character.isDigit(s.charAt(0))) {
            s = "_" + s;
        }
        return s;
    }

    private String join(List<String> xs) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < xs.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append(xs.get(i));
        }
        return sb.toString();
    }
}