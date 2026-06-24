//@category Data Types
//@author ada-l0velace

import java.io.File;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.cparser.C.CParserUtils;
import ghidra.program.model.data.DataTypeManager;
import ghidra.program.model.data.FileDataTypeManager;
import ghidra.program.model.lang.CompilerSpecID;
import ghidra.program.model.lang.LanguageID;

public class HeaderToGdt extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] argv = getScriptArgs();
        if (argv.length < 5) {
            printerr("usage: HeaderToGdt <header.h> <out.gdt> <language-id> <compiler-spec-id> <parser-log:true|false> [include-paths-pathsep|-] [cpp-args...]");
            return;
        }

        File header = new File(argv[0]).getAbsoluteFile();
        File outGdt = new File(argv[1]).getAbsoluteFile();
        String languageId = argv[2];
        String compilerSpecId = argv[3];
        boolean parserLog = Boolean.parseBoolean(argv[4]);

        List<String> includes = new ArrayList<String>();
        if (argv.length >= 6 && argv[5] != null && argv[5].length() > 0 && !argv[5].equals("-")) {
            includes.addAll(Arrays.asList(argv[5].split(java.io.File.pathSeparator)));
        }

        List<String> cargs = new ArrayList<String>();
        for (int i = 6; i < argv.length; i++) {
            if (argv[i] == null || argv[i].length() == 0) {
                continue;
            }
            // Keep parse fast unless the caller explicitly asks for parser logs.
            if (!parserLog && (argv[i].equals("-v") || argv[i].equals("-v6") || argv[i].equals("--verbose"))) {
                continue;
            }
            cargs.add(argv[i]);
        }

        if (!header.isFile()) {
            throw new IllegalArgumentException("header does not exist: " + header);
        }
        if (outGdt.exists() && !outGdt.delete()) {
            throw new IllegalStateException("cannot overwrite existing GDT: " + outGdt);
        }
        File parent = outGdt.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }

        println("[HeaderToGdt] header=" + header);
        println("[HeaderToGdt] out=" + outGdt);
        println("[HeaderToGdt] language=" + languageId + " compiler=" + compilerSpecId);
        println("[HeaderToGdt] parserLog=" + parserLog);

        FileDataTypeManager dtm = FileDataTypeManager.createFileArchive(
            outGdt,
            new LanguageID(languageId),
            new CompilerSpecID(compilerSpecId)
        );

        try {
            Object results = parseHeaderFilesCompat(
                new String[] { header.getAbsolutePath() },
                includes.toArray(new String[includes.size()]),
                cargs.toArray(new String[cargs.size()]),
                dtm
            );
            if (parserLog && results != null) {
                printParseMessages(results, new String[] { header.getAbsolutePath() });
            }
            dtm.save();
            println("[HeaderToGdt] saved " + outGdt + " with " + dtm.getName());
        }
        finally {
            dtm.close();
        }
    }

    /**
     * Ghidra 12 changed CParserUtils overloads. Use reflection so this script can run
     * across Ghidra 11.x/12.x without hard-coding a single parseHeaderFiles signature.
     */
    private Object parseHeaderFilesCompat(String[] headers, String[] includes, String[] cargs, FileDataTypeManager dtm) throws Exception {
        Method best = null;
        Object[] args = null;

        for (Method m : CParserUtils.class.getMethods()) {
            if (!m.getName().equals("parseHeaderFiles")) {
                continue;
            }
            Class<?>[] p = m.getParameterTypes();

            // Ghidra 12 style:
            // parseHeaderFiles(DataTypeManager[] openDTMgrs, String[] files, String[] includes,
            //                  String[] args, DataTypeManager destination, TaskMonitor monitor)
            if (p.length == 6 && p[0].isArray() && p[1].isArray() && p[2].isArray() && p[3].isArray()
                    && p[4].isAssignableFrom(dtm.getClass())) {
                best = m;
                args = new Object[] { new DataTypeManager[0], headers, includes, cargs, dtm, monitor };
                break;
            }

            // Older style:
            // parseHeaderFiles(String[] files, String[] includes, String[] args,
            //                  DataTypeManager destination, TaskMonitor monitor)
            if (p.length == 5 && p[0].isArray() && p[1].isArray() && p[2].isArray()
                    && p[3].isAssignableFrom(dtm.getClass())) {
                best = m;
                args = new Object[] { headers, includes, cargs, dtm, monitor };
            }
        }

        if (best == null) {
            throw new NoSuchMethodException("No compatible CParserUtils.parseHeaderFiles overload found");
        }

        try {
            return best.invoke(null, args);
        }
        catch (InvocationTargetException e) {
            Throwable cause = e.getCause();
            if (cause instanceof Exception) {
                throw (Exception) cause;
            }
            throw e;
        }
    }

    private void printParseMessages(Object results, String[] headers) {
        try {
            Method m = results.getClass().getMethod("getFormattedParseMessage", String[].class);
            Object msg = m.invoke(results, new Object[] { headers });
            if (msg != null) {
                println(msg.toString());
            }
        }
        catch (Throwable t) {
            println(results.toString());
        }
    }
}
