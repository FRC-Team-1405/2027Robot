package frc.robot.lib;

import com.fasterxml.jackson.annotation.JsonFormat.Feature;

import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import frc.robot.constants.FeatureSwitches;

public class FinneyLogger {
    // Get the NetworkTable instance
    private static final NetworkTableInstance ntInstance = NetworkTableInstance.getDefault();

    // Get or create a table for logging
    private static final NetworkTable logTable = ntInstance.getTable("AdvantageScopeLogs");

    // Instance-specific log entry
    private final NetworkTableEntry logEntry;

    // Feature switch is optionally passed in to toggle logging
    private final boolean loggingEnabled;

    // Constructor takes a string to determine the log entry key
    public FinneyLogger(String entryKey) {
        this.loggingEnabled = FeatureSwitches.ENABLE_SUBSYSTEM_DEBUG_PRINTS;
        this.logEntry = logTable.getEntry(entryKey);
        log("loggerInit");
    }

    /*
     * Pass in feature switch from FeatureSwitches
     */
    public FinneyLogger(String entryKey, boolean enableLogging) {
        this.loggingEnabled = enableLogging;
        this.logEntry = logTable.getEntry(entryKey);
        log("loggerInit");
    }

    // Logs a message to the specific log entry
    public void log(String message) {
        if (loggingEnabled) {
            System.out.println(message);
            logEntry.setString(message);
        }
    }

    // Overloaded log method for formatted messages
    public void log(String format, Object... args) {
        if (loggingEnabled) {
            String message = String.format(format, args);
            log(message);
        }
    }
}
