package frc.robot.power;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.DoubleSupplier;
import com.ctre.phoenix6.BaseStatusSignal;
import com.ctre.phoenix6.configs.CurrentLimitsConfigs;
import com.ctre.phoenix6.controls.ControlRequest;
import com.ctre.phoenix6.hardware.TalonFX;
import edu.wpi.first.wpilibj.RobotBase;
import edu.wpi.first.wpilibj.Preferences;
import org.littletonrobotics.conduit.ConduitApi;
import org.littletonrobotics.junction.LogTable;
import org.littletonrobotics.junction.Logger;
import org.littletonrobotics.junction.inputs.LoggableInputs;

/** Read-only power observation. Never changes a motor request or current limit.
 * Register existing motor objects; aliases share one physical identity. Call initialize()
 * after all subsystem constructors, so the readback sees the final configuration.
 */
public final class PowerTelemetry {
    private PowerTelemetry() {}
    private static final Map<String, Device> devices = new LinkedHashMap<>();
    private static final Values distribution = new Values();
    private static final Map<TalonFX, String> owners = new java.util.IdentityHashMap<>();

    public static String identity(String bus, int id) {
        return (bus == null || bus.isBlank() || bus.equals("rio") ? "rio"
                : java.net.URLEncoder.encode(bus, java.nio.charset.StandardCharsets.UTF_8)) + "-" + id;
    }

    public static void register(TalonFX motor, String name, String subsystem) {
        owners.put(motor, name);
        String id = identity(motor.getNetwork().getName(), motor.getDeviceID());
        // Last owner wins (Pickup is constructed after Intake). Preserve its alias.
        Device previous = devices.get(id);
        Device device = new Device(motor, name, subsystem);
        if (previous != null) device.inputs.strings.put("Aliases", previous.inputs.strings.get("Name") + ", " + name);
        devices.put(id, device);
    }

    /** Declare simulated/replay mechanism identities without creating hardware. */
    public static void declare(String bus, int id, String name, String subsystem) {
        devices.putIfAbsent(identity(bus, id), new Device(null, name, subsystem));
    }

    /** Observe the exact request at its call site, including either owner of an alias.
     * Returns the same request unchanged; the existing caller still sends it.
     */
    public static <T extends ControlRequest> T request(TalonFX motor, T request) {
        Device device = devices.get(identity(motor.getNetwork().getName(), motor.getDeviceID()));
        if (device != null) {
            device.observeRequest(request, owners.getOrDefault(motor, "Unknown"));
            device.requestObserved = true;
        }
        return request;
    }

    public static void initialize() {
        for (Device device : devices.values()) device.initialize();
        distribution.numbers.put("ModuleId", Double.NaN);
        distribution.numbers.put("ChannelCount", Double.NaN);
        distribution.booleans.put("Valid", false);
        distribution.strings.put("ValidityBasis", "PDH channel count and voltage plausibility; packet age unavailable");
        distribution.strings.put("BatteryId", "Unknown");
        Preferences.initString("Power/BatteryId", "Unknown");
    }

    /** Call after applying a new configuration, outside the time-critical control loop.
     * Existing limits remain unknown on failure; no retry or motor mutation is performed.
     */
    public static void refreshConfiguration(TalonFX motor) {
        Device device = devices.get(identity(motor.getNetwork().getName(), motor.getDeviceID()));
        if (device != null) device.readConfiguration();
    }

    /** Record the caller's actual apply result, independently of later readback. */
    public static void recordConfigurationApplication(TalonFX motor, com.ctre.phoenix6.StatusCode status) {
        Device device = devices.get(identity(motor.getNetwork().getName(), motor.getDeviceID()));
        if (device != null) device.inputs.strings.put("ConfigApplicationStatus", status.toString());
    }

    public static void periodic() {
        Logger.recordOutput("Power/SchemaVersion", 1);
        Logger.recordOutput("Power/HeartbeatSeconds", Logger.getTimestamp() / 1e6);
        if (RobotBase.isReal()) {
            ConduitApi pd = ConduitApi.getInstance(); // same captured PDH data as built-in AKit logging
            distribution.numbers.put("ModuleId", (double) pd.getPDPModuleId());
            distribution.numbers.put("ChannelCount", (double) pd.getPDPChannelCount());
            // The captured API has no packet timestamp. A plausible value cannot prove freshness.
            boolean valid = pd.getPDPChannelCount() == 24 && pd.getPDPVoltage() > 0;
            distribution.booleans.put("Valid", valid);
            distribution.strings.put("BatteryId", Preferences.getString("Power/BatteryId", "Unknown"));
        }
        Logger.processInputs("Power/Distribution", distribution);
        for (var entry : devices.entrySet()) {
            Device device = entry.getValue();
            if (RobotBase.isReal() && device.motor != null) device.update();
            Logger.processInputs("Power/Motors/" + entry.getKey(), device.inputs);
        }
        PowerStates.periodic();
    }

    static final class Values implements LoggableInputs {
        final Map<String, Double> numbers = new LinkedHashMap<>();
        final Map<String, Boolean> booleans = new LinkedHashMap<>();
        final Map<String, String> strings = new LinkedHashMap<>();
        public void toLog(LogTable table) {
            numbers.forEach((k, v) -> table.put(k, v.doubleValue()));
            booleans.forEach((k, v) -> table.put(k, v.booleanValue()));
            strings.forEach(table::put);
        }
        public void fromLog(LogTable table) {
            numbers.replaceAll((k, v) -> table.get(k, Double.NaN));
            booleans.replaceAll((k, v) -> table.get(k, false));
            strings.replaceAll((k, v) -> table.get(k, "Unknown"));
        }
    }

    private static final class Device {
        final TalonFX motor;
        final Values inputs = new Values();
        final Map<String, BaseStatusSignal> signals = new LinkedHashMap<>();
        final Map<String, DoubleSupplier> values = new LinkedHashMap<>();
        boolean requestObserved;
        Device(TalonFX motor, String name, String subsystem) {
            this.motor = motor;
            for (String key : new String[]{"SupplyCurrentAmps", "StatorCurrentAmps", "TorqueCurrentAmps",
                    "SupplyVoltage", "OutputVoltage", "DutyCycle", "VelocityRPS", "PositionRots",
                    "ClosedLoopError", "ClosedLoopReference", "SignalAgeSeconds", "StatorLimitAmps",
                    "SupplyLimitAmps", "SupplyLowerLimitAmps", "SupplyLowerTimeSeconds", "DeviceId",
                    "RequestedSetpoint", "RequestedAmps", "RequestTimestampSeconds", "TemperatureCelsius"}) {
                inputs.numbers.put(key, Double.NaN);
            }
            for (String key : new String[]{"Valid", "SupplyLimited", "StatorLimited", "Undervoltage",
                    "StickySupplyLimited", "StickyStatorLimited", "StickyFaultsValid", "ConfigValid", "SupplyLimitEnabled", "StatorLimitEnabled"}) {
                inputs.booleans.put(key, false);
            }
            for (String key : new String[]{"Name", "Subsystem", "Bus", "Aliases", "Follower", "ControlMode",
                    "Request", "ConfigStatus", "ConfigApplicationStatus", "SignalStatus", "RequestUnits", "RequestOwner", "ObservedControlMode"}) inputs.strings.put(key, "Unknown");
            inputs.strings.put("Name", name);
            inputs.strings.put("Subsystem", subsystem);
            if (motor != null) {
                inputs.numbers.put("DeviceId", (double) motor.getDeviceID());
                inputs.strings.put("Bus", motor.getNetwork().getName());
            }
        }
        void signal(String name, BaseStatusSignal signal, DoubleSupplier value) {
            signals.put(name, signal);
            values.put(name, value);
        }
        void initialize() {
            if (motor == null || !RobotBase.isReal()) return;
            var supply = motor.getSupplyCurrent();
            signal("SupplyCurrentAmps", supply, supply::getValueAsDouble);
            var stator = motor.getStatorCurrent();
            signal("StatorCurrentAmps", stator, stator::getValueAsDouble);
            var torque = motor.getTorqueCurrent();
            signal("TorqueCurrentAmps", torque, torque::getValueAsDouble);
            var supplyV = motor.getSupplyVoltage();
            signal("SupplyVoltage", supplyV, supplyV::getValueAsDouble);
            var outputV = motor.getMotorVoltage();
            signal("OutputVoltage", outputV, outputV::getValueAsDouble);
            var duty = motor.getDutyCycle();
            signal("DutyCycle", duty, duty::getValueAsDouble);
            var speed = motor.getVelocity();
            signal("VelocityRPS", speed, speed::getValueAsDouble);
            var position = motor.getPosition();
            signal("PositionRots", position, position::getValueAsDouble);
            var error = motor.getClosedLoopError();
            signal("ClosedLoopError", error, error::getValueAsDouble);
            var reference = motor.getClosedLoopReference();
            signal("ClosedLoopReference", reference, reference::getValueAsDouble);
            var supplyLimit = motor.getFault_SupplyCurrLimit();
            signal("SupplyLimited", supplyLimit, () -> supplyLimit.getValue() ? 1 : 0);
            var statorLimit = motor.getFault_StatorCurrLimit();
            signal("StatorLimited", statorLimit, () -> statorLimit.getValue() ? 1 : 0);
            var under = motor.getFault_Undervoltage();
            signal("Undervoltage", under, () -> under.getValue() ? 1 : 0);
            signals.put("ObservedControlMode", motor.getControlMode());
            // Raise only slow signals; preserve existing 100/250 Hz motion signals.
            for (BaseStatusSignal signal : signals.values()) {
                if (signal.getAppliedUpdateFrequency() < 50) signal.setUpdateFrequency(50);
            }
            motor.getDeviceTemp().setUpdateFrequency(4);
            motor.getStickyFault_SupplyCurrLimit().setUpdateFrequency(4);
            motor.getStickyFault_StatorCurrLimit().setUpdateFrequency(4);
            readConfiguration();
        }
        void readConfiguration() {
            if (motor == null || !RobotBase.isReal()) return;
            CurrentLimitsConfigs config = new CurrentLimitsConfigs();
            var status = motor.getConfigurator().refresh(config);
            inputs.strings.put("ConfigStatus", status.toString());
            inputs.booleans.put("ConfigValid", status.isOK());
            inputs.numbers.put("StatorLimitAmps", status.isOK() ? config.StatorCurrentLimit : Double.NaN);
            inputs.numbers.put("SupplyLimitAmps", status.isOK() ? config.SupplyCurrentLimit : Double.NaN);
            inputs.numbers.put("SupplyLowerLimitAmps", status.isOK() ? config.SupplyCurrentLowerLimit : Double.NaN);
            inputs.numbers.put("SupplyLowerTimeSeconds", status.isOK() ? config.SupplyCurrentLowerTime : Double.NaN);
            inputs.booleans.put("SupplyLimitEnabled", status.isOK() && config.SupplyCurrentLimitEnable);
            inputs.booleans.put("StatorLimitEnabled", status.isOK() && config.StatorCurrentLimitEnable);
        }
        void update() {
            var status = BaseStatusSignal.refreshAll(signals.values().toArray(BaseStatusSignal[]::new));
            double age = signals.values().stream().mapToDouble(s -> s.getTimestamp().getLatency()).max().orElse(Double.POSITIVE_INFINITY);
            boolean valid = status.isOK() && age <= 0.1;
            inputs.booleans.put("Valid", valid);
            inputs.numbers.put("SignalAgeSeconds", age);
            inputs.strings.put("SignalStatus", status.toString());
            inputs.strings.put("ObservedControlMode", valid ? motor.getControlMode(false).getValue().toString() : "Unknown");
            var temperature = motor.getDeviceTemp();
            inputs.numbers.put("TemperatureCelsius", temperature.getStatus().isOK() && temperature.getTimestamp().getLatency() <= 1.0
                    ? temperature.getValueAsDouble() : Double.NaN);
            values.forEach((key, supplier) -> {
                if (inputs.booleans.containsKey(key)) inputs.booleans.put(key, valid && supplier.getAsDouble() != 0);
                else inputs.numbers.put(key, valid ? supplier.getAsDouble() : Double.NaN);
            });
            var stickySupply = motor.getStickyFault_SupplyCurrLimit();
            var stickyStator = motor.getStickyFault_StatorCurrLimit();
            boolean stickyValid = stickySupply.getStatus().isOK() && stickyStator.getStatus().isOK()
                    && stickySupply.getTimestamp().getLatency() <= 1.0 && stickyStator.getTimestamp().getLatency() <= 1.0;
            inputs.booleans.put("StickyFaultsValid", stickyValid);
            inputs.booleans.put("StickySupplyLimited", stickyValid && stickySupply.getValue());
            inputs.booleans.put("StickyStatorLimited", stickyValid && stickyStator.getValue());
            if (!requestObserved) observeRequest(motor.getAppliedControl(), inputs.strings.get("Name"));
        }
        void observeRequest(ControlRequest request, String owner) {
            inputs.strings.put("ControlMode", request.getName());
            inputs.strings.put("Request", request.getControlInfo().toString());
            inputs.strings.put("Follower", request.getName().contains("Follower") ? request.getControlInfo().toString() : "None");
            inputs.strings.put("RequestOwner", owner);
            inputs.numbers.put("RequestTimestampSeconds", Logger.getTimestamp() / 1e6);
            Map<String, String> info = request.getControlInfo();
            String field = info.containsKey("Velocity") ? "Velocity" : info.containsKey("Position") ? "Position" : "Output";
            String unit = field.equals("Velocity") ? "rotations/s" : field.equals("Position") ? "rotations"
                    : request.getName().contains("TorqueCurrent") ? "A" : request.getName().contains("Voltage") ? "V"
                    : request.getName().contains("DutyCycle") ? "duty cycle" : "Unknown";
            double requested = Double.NaN;
            try { requested = Double.parseDouble(info.getOrDefault(field, "NaN")); }
            catch (NumberFormatException ignored) { /* Native request map remains available. */ }
            inputs.numbers.put("RequestedSetpoint", requested);
            inputs.numbers.put("RequestedAmps", unit.equals("A") ? requested : Double.NaN);
            inputs.strings.put("RequestUnits", unit);
        }
    }
}
