import wcontour.Contour;
import wcontour.global.*;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * Ground-truth driver for the wContour subroutine chain used by the Xunteng
 * equiSurfaceImg reference code:
 *
 *   tracingBorders -> tracingContourLines -> smoothLines -> tracingPolygons
 *
 * Input : plain whitespace-token text file (see readInput below)
 * Output: JSON with every intermediate stage so a port can be validated layer by layer
 */
public class WContourDriver {

    // ---------------------------------------------------------------- helpers

    static String num(double d) {
        if (Double.isNaN(d) || Double.isInfinite(d)) {
            return "null";
        }
        return Double.toString(d);
    }

    static String ptList(List<PointD> pl) {
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < pl.size(); i++) {
            if (i > 0) b.append(',');
            PointD p = pl.get(i);
            b.append('[').append(num(p.X)).append(',').append(num(p.Y)).append(']');
        }
        return b.append(']').toString();
    }

    static String polyLineJson(PolyLine l) {
        StringBuilder b = new StringBuilder();
        b.append('{');
        b.append("\"value\":").append(num(l.Value)).append(',');
        b.append("\"type\":").append(l.Type == null ? "null" : "\"" + l.Type + "\"").append(',');
        b.append("\"borderIdx\":").append(l.BorderIdx).append(',');
        b.append("\"npoints\":").append(l.PointList.size()).append(',');
        b.append("\"points\":").append(ptList(l.PointList));
        b.append('}');
        return b.toString();
    }

    static String extentJson(Extent e) {
        if (e == null) return "null";
        return "[" + num(e.xMin) + "," + num(e.yMin) + "," + num(e.xMax) + "," + num(e.yMax) + "]";
    }

    static String polygonJson(Polygon p) {
        StringBuilder b = new StringBuilder();
        b.append('{');
        b.append("\"isBorder\":").append(p.IsBorder).append(',');
        b.append("\"isInnerBorder\":").append(p.IsInnerBorder).append(',');
        b.append("\"lowValue\":").append(num(p.LowValue)).append(',');
        b.append("\"highValue\":").append(num(p.HighValue)).append(',');
        b.append("\"isClockWise\":").append(p.IsClockWise).append(',');
        b.append("\"startPointIdx\":").append(p.StartPointIdx).append(',');
        b.append("\"isHighCenter\":").append(p.IsHighCenter).append(',');
        b.append("\"area\":").append(num(p.Area)).append(',');
        b.append("\"extent\":").append(extentJson(p.Extent)).append(',');
        b.append("\"nHoles\":").append(p.HoleLines.size()).append(',');
        b.append("\"outline\":").append(polyLineJson(p.OutLine)).append(',');
        b.append("\"holes\":[");
        for (int i = 0; i < p.HoleLines.size(); i++) {
            if (i > 0) b.append(',');
            b.append(polyLineJson(p.HoleLines.get(i)));
        }
        b.append("]}");
        return b.toString();
    }

    static String borderJson(Border bo) {
        StringBuilder b = new StringBuilder();
        b.append('{');
        b.append("\"lineNum\":").append(bo.getLineNum()).append(',');
        b.append("\"lines\":[");
        for (int i = 0; i < bo.getLineNum(); i++) {
            if (i > 0) b.append(',');
            BorderLine bl = bo.LineList.get(i);
            b.append('{');
            b.append("\"area\":").append(num(bl.area)).append(',');
            b.append("\"extent\":").append(extentJson(bl.extent)).append(',');
            b.append("\"isOutLine\":").append(bl.isOutLine).append(',');
            b.append("\"isClockwise\":").append(bl.isClockwise).append(',');
            b.append("\"npoints\":").append(bl.pointList.size()).append(',');
            b.append("\"points\":").append(ptList(bl.pointList)).append(',');
            b.append("\"ij\":[");
            for (int k = 0; k < bl.ijPointList.size(); k++) {
                if (k > 0) b.append(',');
                IJPoint ij = bl.ijPointList.get(k);
                b.append('[').append(ij.I).append(',').append(ij.J).append(']');
            }
            b.append("]}");
        }
        b.append("]}");
        return b.toString();
    }

    // ------------------------------------------------------------------ input

    static String[] tokens;

    static int ti;

    static String next() {
        return tokens[ti++];
    }

    static int nextInt() {
        return Integer.parseInt(next());
    }

    static double nextDouble() {
        return Double.parseDouble(next());
    }

    static void expect(String s) {
        String t = next();
        if (!t.equals(s)) {
            throw new IllegalArgumentException("expected token '" + s + "' but got '" + t + "'");
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: WContourDriver <input.txt> <output.json>");
            System.exit(2);
        }
        String txt = new String(java.nio.file.Files.readAllBytes(new File(args[0]).toPath()),
                StandardCharsets.UTF_8);
        tokens = txt.trim().split("\\s+");
        ti = 0;

        expect("M");
        int m = nextInt();
        expect("N");
        int n = nextInt();
        expect("UNDEF");
        double undef = nextDouble();
        expect("NC");
        int nc = nextInt();

        expect("X");
        double[] X = new double[n];
        for (int j = 0; j < n; j++) X[j] = nextDouble();
        expect("Y");
        double[] Y = new double[m];
        for (int i = 0; i < m; i++) Y[i] = nextDouble();
        expect("CONTOUR");
        double[] contour = new double[nc];
        for (int k = 0; k < nc; k++) contour[k] = nextDouble();

        expect("GRID");
        double[][] S0 = new double[m][n];
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                S0[i][j] = nextDouble();
            }
        }

        // ---------------------------------------------------------- algorithm
        int[][] S1 = new int[m][n];
        List<Border> borders = Contour.tracingBorders(S0, X, Y, S1, undef);

        List<PolyLine> cLines = Contour.tracingContourLines(S0, X, Y, nc, contour, undef, borders, S1);

        // snapshot contour lines BEFORE smoothLines (smoothLines mutates PointList in place)
        List<List<double[]>> preSmooth = new ArrayList<>();
        List<String> preMeta = new ArrayList<>();
        for (PolyLine l : cLines) {
            List<double[]> pts = new ArrayList<>();
            for (PointD p : l.PointList) pts.add(new double[]{p.X, p.Y});
            preSmooth.add(pts);
            preMeta.add(num(l.Value) + "|" + l.Type + "|" + l.BorderIdx);
        }

        List<PolyLine> sLines = Contour.smoothLines(cLines);

        List<Polygon> polys = Contour.tracingPolygons(S0, sLines, borders, contour);

        // ------------------------------------------------------------- output
        StringBuilder o = new StringBuilder();
        o.append('{');
        o.append("\"m\":").append(m).append(",\"n\":").append(n).append(',');
        o.append("\"undef\":").append(num(undef)).append(',');
        o.append("\"nc\":").append(nc).append(',');
        o.append("\"contour\":[");
        for (int k = 0; k < nc; k++) {
            if (k > 0) o.append(',');
            o.append(num(contour[k]));
        }
        o.append("],");

        o.append("\"S1\":[");
        for (int i = 0; i < m; i++) {
            if (i > 0) o.append(',');
            o.append('[');
            for (int j = 0; j < n; j++) {
                if (j > 0) o.append(',');
                o.append(S1[i][j]);
            }
            o.append(']');
        }
        o.append("],");

        o.append("\"borders\":[");
        for (int i = 0; i < borders.size(); i++) {
            if (i > 0) o.append(',');
            o.append(borderJson(borders.get(i)));
        }
        o.append("],");

        o.append("\"contourLines\":[");
        for (int i = 0; i < preSmooth.size(); i++) {
            if (i > 0) o.append(',');
            String[] mm = preMeta.get(i).split("\\|", -1);
            o.append("{\"value\":").append(mm[0])
                    .append(",\"type\":").append("null".equals(mm[1]) ? "null" : "\"" + mm[1] + "\"")
                    .append(",\"borderIdx\":").append(mm[2])
                    .append(",\"npoints\":").append(preSmooth.get(i).size())
                    .append(",\"points\":[");
            List<double[]> pts = preSmooth.get(i);
            for (int k = 0; k < pts.size(); k++) {
                if (k > 0) o.append(',');
                o.append('[').append(num(pts.get(k)[0])).append(',').append(num(pts.get(k)[1])).append(']');
            }
            o.append("]}");
        }
        o.append("],");

        o.append("\"smoothLines\":[");
        for (int i = 0; i < sLines.size(); i++) {
            if (i > 0) o.append(',');
            o.append(polyLineJson(sLines.get(i)));
        }
        o.append("],");

        o.append("\"polygons\":[");
        for (int i = 0; i < polys.size(); i++) {
            if (i > 0) o.append(',');
            o.append(polygonJson(polys.get(i)));
        }
        o.append("]}");

        try (Writer w = new OutputStreamWriter(new FileOutputStream(args[1]), StandardCharsets.UTF_8)) {
            w.write(o.toString());
        }
        System.out.println("OK m=" + m + " n=" + n + " borders=" + borders.size()
                + " contourLines=" + cLines.size() + " smoothLines=" + sLines.size()
                + " polygons=" + polys.size());
    }
}
