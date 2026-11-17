import java.awt.*;
import java.nio.file.*;
import java.util.*;
import javax.swing.*;

/** Teaching simulator, not deployable robot code. Run: java RobotLab.java */
public class RobotLab {
  // STUDENT WORK AREA. Keep edits here until the refactoring lesson.
  static class StudentController {
    double kP = 0.0; // volts per meter: lessons 07-08
    double kD = 0.0; // volts per (meter/second)
    double kG = 0.0; // volts to counter gravity in this teaching model

    double metersFromRotations(double motorRotations) {
      // Lesson 02: 10 motor turns = 1 drum turn; drum circumference = 0.20 m.
      return motorRotations;
    }
    double limitVoltage(double volts, double heightMeters) {
      // Lessons 03-04: clamp to +/-6 V, then block motion beyond 0.05..1.45 m.
      return volts;
    }
    boolean atGoal(double target, double height, double velocity) {
      // Lesson 07: error <= 0.03 m AND speed <= 0.05 m/s.
      return false;
    }
    double calculate(boolean enabled, boolean automatic, double manualVolts,
        double targetMeters, double heightMeters, double velocityMetersPerSecond) {
      if (!enabled) return 0.0;
      double requested = manualVolts;
      // Lesson 07: if automatic, use kP * (targetMeters - heightMeters).
      // Lesson 08: add kG and subtract kD * velocityMetersPerSecond in automatic mode.
      return limitVoltage(requested, heightMeters);
    }
  }
  // END STUDENT WORK AREA. Mentor-supplied support code below.
  static final double DT = 0.02;
  static class Plant {
    double height = 0.20, velocity = 0;
    void step(double volts) {
      // Simplified model: a = 2*V - 1 - 3*v. Not a calibrated elevator model.
      double acceleration = 2.0 * volts - 1.0 - 3.0 * velocity;
      velocity += acceleration * DT;
      height += velocity * DT;
      if (height < 0) { height = 0; velocity = Math.max(0, velocity); }
      if (height > 1.5) { height = 1.5; velocity = Math.min(0, velocity); }
    }
  }
  record Sample(double time, double target, double height, double velocity,
                double requested, double applied, boolean enabled, boolean atGoal) {}
  final StudentController controller = new StudentController();
  final Plant plant = new Plant();
  final java.util.List<Sample> samples = new ArrayList<>();
  int ticks;
  String scenario = "auto";
  Sample step(boolean enabled, boolean automatic, double manual, double target) {
    double requested = controller.calculate(enabled, automatic, manual, target,
        plant.height, plant.velocity);
    // Simulated motor hardware saturates at +/-12 V. Students implement the 6 V policy.
    if (!Double.isFinite(requested)) throw new IllegalStateException("Non-finite voltage");
    double applied = Math.max(-12, Math.min(12, requested));
    // The simulator also models the hardware disable interlock.
    if (!enabled) applied = 0;
    plant.step(applied);
    Sample s = new Sample(++ticks * DT, target, plant.height, plant.velocity,
        requested, applied, enabled, controller.atGoal(target, plant.height, plant.velocity));
    samples.add(s);
    return s;
  }
  Sample scenarioStep() {
    double t = ticks * DT;
    double target = t < 4 ? 0.8 : t < 8 ? 1.2 : 0.3;
    return step(!scenario.equals("disabled"), !scenario.equals("manual"), 2.0, target);
  }
  void export(Path path) throws Exception {
    java.util.List<String> lines = new ArrayList<>();
    lines.add("time_s,target_m,height_m,velocity_mps,requested_V,applied_V,enabled,at_goal");
    for (Sample s : samples) lines.add(String.format(Locale.ROOT,
        "%.3f,%.4f,%.4f,%.4f,%.4f,%.4f,%s,%s", s.time(), s.target(), s.height(),
        s.velocity(), s.requested(), s.applied(), s.enabled(), s.atGoal()));
    Files.write(path, lines);
  }
  void gui() {
    JFrame frame = new JFrame("Robot Lab: simulated elevator");
    frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
    JCheckBox enabled = new JCheckBox("Enabled");
    JCheckBox automatic = new JCheckBox("Automatic");
    JSlider manual = new JSlider(-60, 60, 0);
    JSlider target = new JSlider(5, 145, 80);
    JLabel status = new JLabel("Disabled. Enable to test.");
    JPanel controls = new JPanel();
    JButton reset = new JButton("Reset"), export = new JButton("Export CSV");
    controls.add(enabled); controls.add(automatic);
    controls.add(new JLabel("Manual volts /10")); controls.add(manual);
    controls.add(new JLabel("Target cm")); controls.add(target);
    controls.add(reset); controls.add(export);
    JPanel drawing = new JPanel() {
      protected void paintComponent(Graphics g) {
        super.paintComponent(g);
        int base = getHeight()-35;
        g.setColor(Color.DARK_GRAY); g.fillRect(75, 20, 12, base-20);
        int y = base-(int)(plant.height/1.5*(base-20));
        int goal = base-(int)(target.getValue()/150.0*(base-20));
        g.setColor(new Color(20,140,80)); g.drawLine(45,goal,155,goal);
        g.setColor(new Color(30,110,220)); g.fillRect(55,y-7,70,14);
        g.setColor(Color.DARK_GRAY); g.drawString("0 m",20,base);
        g.drawString("1.5 m",15,25);
        // Target and measured height history, last 12 seconds.
        int left=210, right=getWidth()-20, top=25, bottom=base;
        g.drawRect(left,top,Math.max(1,right-left),Math.max(1,bottom-top));
        int start=Math.max(0,samples.size()-600);
        for(int i=start+1;i<samples.size();i++) {
          Sample a=samples.get(i-1), b=samples.get(i);
          int x1=left+(i-1-start)*(right-left)/600;
          int x2=left+(i-start)*(right-left)/600;
          g.setColor(new Color(20,140,80));
          g.drawLine(x1,bottom-(int)(a.target()/1.5*(bottom-top)),x2,bottom-(int)(b.target()/1.5*(bottom-top)));
          g.setColor(new Color(30,110,220));
          g.drawLine(x1,bottom-(int)(a.height()/1.5*(bottom-top)),x2,bottom-(int)(b.height()/1.5*(bottom-top)));
        }
        g.setColor(Color.DARK_GRAY); g.drawString("Green: target   Blue: measured height",left,17);
      }
    };
    reset.addActionListener(e -> { enabled.setSelected(false); plant.height=.20;
      plant.velocity=0; samples.clear(); ticks=0; });
    export.addActionListener(e -> {
      JFileChooser chooser = new JFileChooser();
      chooser.setSelectedFile(new java.io.File("run.csv"));
      if(chooser.showSaveDialog(frame)==JFileChooser.APPROVE_OPTION) try {
        export(chooser.getSelectedFile().toPath()); status.setText("Saved CSV");
      } catch(Exception ex) { status.setText(ex.toString()); }
    });
    new javax.swing.Timer(20, e -> {
      Sample s=step(enabled.isSelected(),automatic.isSelected(),manual.getValue()/10.0,target.getValue()/100.0);
      status.setText(String.format(Locale.ROOT,
          "t=%.2f s | height=%.3f m | speed=%.3f m/s | requested=%.2f V | applied=%.2f V | atGoal=%s",
          s.time(),s.height(),s.velocity(),s.requested(),s.applied(),s.atGoal()));
      drawing.repaint();
    }).start();
    frame.add(controls,BorderLayout.NORTH); frame.add(drawing,BorderLayout.CENTER);
    frame.add(status,BorderLayout.SOUTH); frame.setSize(1100,550); frame.setVisible(true);
  }
  static int failures;
  static void check(String name, boolean pass) {
    System.out.println((pass?"PASS ":"FAIL ")+name); if(!pass) failures++;
  }
  static boolean close(double a,double b) { return Math.abs(a-b)<1e-9; }
  static void tests(String lesson) {
    StudentController c=new StudentController();
    switch(lesson) {
      case "02":
        check("50 motor rotations -> 1 meter",close(c.metersFromRotations(50),1));
        check("negative rotations preserve direction",close(c.metersFromRotations(-10),-.2)); break;
      case "03":
        check("clamp +9 to +6",close(c.limitVoltage(9,.7),6));
        check("clamp -9 to -6",close(c.limitVoltage(-9,.7),-6));
        check("keep +2",close(c.limitVoltage(2,.7),2)); break;
      case "04":
        check("block down at lower limit",close(c.limitVoltage(-2,.05),0));
        check("allow up at lower limit",close(c.limitVoltage(2,.05),2));
        check("block up at upper limit",close(c.limitVoltage(2,1.45),0));
        check("allow down at upper limit",close(c.limitVoltage(-2,1.45),-2));
        check("disabled returns zero",close(c.calculate(false,true,3,1,.5,.1),0)); break;
      case "07":
        check("small error and speed are at goal",c.atGoal(.8,.78,.02));
        check("high speed is not at goal",!c.atGoal(.8,.8,.2));
        check("large negative error is not at goal",!c.atGoal(.3,.8,0));
        c.kP=4; c.kD=0; c.kG=0;
        check("P control direction and magnitude",close(c.calculate(true,true,0,.8,.3,0),2)); break;
      case "08":
        c.kP=4; c.kD=2; c.kG=.5;
        check("gravity hold at rest",close(c.calculate(true,true,0,.8,.8,0),.5));
        check("damping opposes positive speed",close(c.calculate(true,true,0,.8,.8,.1),.3));
        check("manual mode does not add gravity",close(c.calculate(true,false,2,.8,.8,.1),2)); break;
      default: throw new IllegalArgumentException("Tests available: 02 03 04 07 08");
    }
    if(failures>0) System.exit(1);
  }
  public static void main(String[] args) throws Exception {
    if(args.length>0 && args[0].equals("--test")) { tests(args[1]); return; }
    RobotLab lab=new RobotLab();
    if(args.length>0 && args[0].equals("--headless")) {
      lab.scenario=args.length>1?args[1]:"auto";
      if(!Set.of("auto","manual","disabled").contains(lab.scenario))
        throw new IllegalArgumentException("Scenario must be auto, manual, or disabled");
      for(int i=0;i<600;i++) lab.scenarioStep();
      Path path=Path.of(args.length>2?args[2]:"run.csv"); lab.export(path);
      System.out.println("Saved 600 samples to "+path); return;
    }
    SwingUtilities.invokeLater(lab::gui);
  }
}
