package frc.robot.util;

import java.util.Optional;

import edu.wpi.first.hal.simulation.DriverStationDataJNI;
import edu.wpi.first.networktables.BooleanPublisher;
import edu.wpi.first.networktables.BooleanTopic;
import edu.wpi.first.networktables.DoublePublisher;
import edu.wpi.first.networktables.DoubleTopic;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StringPublisher;
import edu.wpi.first.networktables.StringTopic;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.RobotBase;

/**
 * A utility class about which period of the game we're in.
 * 
 * @author Dylan Wilson
 */
public final class GamePeriod {
    /**
     * A period of the game.
     */
    private enum Period {
        // Auto (total 0:20 / 20 seconds)
        AUTO,

        // Teleop (total 2:20 / 140 seconds)
        TRANSITION_SHIFT, // 2:20 to 2:10 (140 to 130 seconds)
        SHIFT_1, // 2:10 to 1:45 (130 to 105 seconds)
        SHIFT_2, // 1:45 to 1:20 (105 to 80 seconds)
        SHIFT_3, // 1:20 to 0:55 (80 to 55 seconds)
        SHIFT_4, // 0:55 to 0:30 (55 to 30 seconds)
        END_GAME, // 0:30 to 0:00 (30 to 0 seconds)

        NOT_IN_MATCH;

        @Override
        public String toString() {
            switch (this) {
                case AUTO:
                    return "Auto";
                case TRANSITION_SHIFT:
                    return "Transition Shift";
                case SHIFT_1:
                    return "Shift 1";
                case SHIFT_2:
                    return "Shift 2";
                case SHIFT_3:
                    return "Shift 3";
                case SHIFT_4:
                    return "Shift 4";
                case END_GAME:
                    return "End Game";
                case NOT_IN_MATCH:
                    return "Not in Match";
                default:
                    return "Invalid";
            }
        }
    }

    /**
     * A listener for when periods change.
     */
    @FunctionalInterface
    public static interface Listener {
        public void run();
    }
    // EXAMPLE CODE TO USE LISTENER (likely in Robot.java constructor)
    // GamePeriod.setListener(() -> {
    // System.out.println("Period has changed, do stuff");
    // });

    /**
     * Listener singleton.
     */
    private static Listener periodChangeListener;
    private static Listener periodChangeWarningListener;

    // Publishers for Elastic dashboard
    private static DoublePublisher matchTimePublisher;
    private static StringPublisher alliancePublisher;
    private static StringPublisher periodPublisher;
    private static BooleanPublisher isActivePublisher;
    private static StringPublisher gameDataPublisher;
    private static DoublePublisher periodTimePublisher;

    private static String gameData = null;

    /**
     * Remembers previous period for hasPeriodChanged()
     */
    private static Period previousPeriod = Period.NOT_IN_MATCH;
    private static double previousPeriodTimeRemaining = -1.0;

    public static void setPeriodChangeListener(Listener l) {
        periodChangeListener = l;
    }

    public static void setPeriodChangeWarningListener(Listener l) {
        periodChangeWarningListener = l;
    }

    /**
     * Returns which period we are in based on the DriverStation's match time.
     * 
     * @return A period of the game.
     */
    public static Period getPeriod() {
        final double secondsRemaining = DriverStation.getMatchTime();

        if (DriverStation.isAutonomous()) {
            if (0.0 <= secondsRemaining && secondsRemaining <= 20.0) {
                return Period.AUTO;
            } else {
                return Period.NOT_IN_MATCH;
            }
        } else if (DriverStation.isTeleop()) {
            if (130.0 <= secondsRemaining && secondsRemaining <= 140.0) {
                return Period.TRANSITION_SHIFT;
            } else if (105.0 <= secondsRemaining && secondsRemaining <= 130.0) {
                return Period.SHIFT_1;
            } else if (80.0 <= secondsRemaining && secondsRemaining <= 105.0) {
                return Period.SHIFT_2;
            } else if (55.0 <= secondsRemaining && secondsRemaining <= 80.0) {
                return Period.SHIFT_3;
            } else if (30.0 <= secondsRemaining && secondsRemaining <= 55.0) {
                return Period.SHIFT_4;
            } else if (0.0 <= secondsRemaining && secondsRemaining <= 30.0) {
                return Period.END_GAME;
            } else {
                return Period.NOT_IN_MATCH;
            }
        }

        return Period.NOT_IN_MATCH;
    }

    /**
     * Returns whether or not our hub is currently active based on the current game
     * period.
     * 
     * @param alliance Our alliance(red/blue)
     * @return {@code true} if our hub is active, {@code false} if inactive, and
     *         {@code Optional.empty()} otherwise.
     */
    public static Optional<Boolean> isHubActive() {
        final Optional<DriverStation.Alliance> alliance = DriverStation.getAlliance();

        if (!alliance.isPresent()) {
            return Optional.empty();
        }

        final String rawGameData = DriverStation.getGameSpecificMessage();
        if (rawGameData.length() == 0) {
            // Code for no data received yet
            return Optional.empty();
        }

        if (gameData == null) {
            gameData = rawGameData;

        }

        final Period period = getPeriod();

        if (period == Period.AUTO || period == Period.TRANSITION_SHIFT || period == Period.END_GAME) {
            return Optional.of(true);
        }

        final boolean isBlue = alliance.get() == DriverStation.Alliance.Blue;
        final char inactiveAllianceChar = rawGameData.charAt(0);
        final boolean isActive = (isBlue && inactiveAllianceChar == 'R' || !isBlue && inactiveAllianceChar == 'B')
                ? (period == Period.SHIFT_1 || period == Period.SHIFT_3)
                : (period == Period.SHIFT_2 || period == Period.SHIFT_4);

        return Optional.of(isActive);
    }

    /**
     * Returns how much time is remaining until the next period.
     * 
     * @return How much time is remaining.
     */
    public static double periodTimeRemaining() {
        final double secondsRemaining = DriverStation.getMatchTime();
        final Period period = getPeriod();

        switch (period) {
            case AUTO:
                return secondsRemaining;
            case TRANSITION_SHIFT:
                return secondsRemaining - 130.0; // 140 + 10
            case SHIFT_1:
                return secondsRemaining - 105.0;
            case SHIFT_2:
                return secondsRemaining - 80.0;
            case SHIFT_3:
                return secondsRemaining - 55.0;
            case SHIFT_4:
                return secondsRemaining - 30.0;
            case END_GAME:
                return secondsRemaining;
            case NOT_IN_MATCH:
            default:
                return -1.0;
        }
    }

    /**
     * The period changing action that the Listener listens for. If the period has
     * changed, the listener runs it's action. Put this method in robotPeriodic or
     * something alike.
     */
    public static void hasPeriodChanged() {
        final Period currentPeriod = getPeriod();

        // basically instantiate previousPeriod
        if (previousPeriod == Period.NOT_IN_MATCH) {
            previousPeriod = currentPeriod;
        }

        if (currentPeriod != previousPeriod) {
            previousPeriod = currentPeriod;
            if (periodChangeListener != null) {
                periodChangeListener.run();
            }
        }
    }

    public static void hasPeriodChangeWarningOccurred() {
        final double currentPeriodTimeRemaining = periodTimeRemaining();

        // instantiate previousPeriodTimeRemaining
        if (previousPeriodTimeRemaining == -1.0) {
            previousPeriodTimeRemaining = currentPeriodTimeRemaining;
        }

        if (currentPeriodTimeRemaining < 10.0 && previousPeriodTimeRemaining >= 10.0) {
            // warn the driver that a period change is imminent (10 second warning)
            if (periodChangeWarningListener != null) {
                periodChangeWarningListener.run();
            }
        }

        previousPeriodTimeRemaining = currentPeriodTimeRemaining;
    }

    /**
     * Initiates dashboard values for Elastic for simulation purposes in Robot.java.
     */
    public static void elasticInit() {
        // Set up NetworkTable's publishers
        NetworkTable table = NetworkTableInstance.getDefault().getTable("GamePeriod");

        DoubleTopic matchTimeTopic = table.getDoubleTopic("MatchTime");
        matchTimePublisher = matchTimeTopic.publish();

        StringTopic allianceTopic = table.getStringTopic("Alliance");
        alliancePublisher = allianceTopic.publish();

        StringTopic periodTopic = table.getStringTopic("Period");
        periodPublisher = periodTopic.publish();

        BooleanTopic isActiveTopic = table.getBooleanTopic("IsHubActive");
        isActivePublisher = isActiveTopic.publish();

        StringTopic gameDataTopic = table.getStringTopic("GameData");
        gameDataPublisher = gameDataTopic.publish();

        DoubleTopic periodTimeTopic = table.getDoubleTopic("PeriodTimeRemaining");
        periodTimePublisher = periodTimeTopic.publish();
    }

    /**
     * Updates Elastic dashboard values periodically for simulation purposes in
     * Robot.java.
     */
    public static void elasticPeriodic() {
        double matchTimeRemaining = DriverStation.getMatchTime();
        matchTimePublisher.set(matchTimeRemaining);

        Optional<DriverStation.Alliance> alliance = DriverStation.getAlliance();
        String allianceString;
        if (alliance.equals(Optional.of(DriverStation.Alliance.Blue))) {
            allianceString = "Blue";
        } else if (alliance.equals(Optional.of(DriverStation.Alliance.Red))) {
            allianceString = "Red";
        } else if (alliance.equals(Optional.empty())) {
            allianceString = "Empty";
        } else {
            allianceString = "Error";
        }
        alliancePublisher.set(allianceString);

        GamePeriod.Period period = GamePeriod.getPeriod();
        String periodString = period.toString();
        periodPublisher.set(periodString);
        hasPeriodChanged();
        hasPeriodChangeWarningOccurred();

        Optional<Boolean> isActive = GamePeriod.isHubActive();
        boolean isActiveValue = isActive.orElse(false);
        isActivePublisher.set(isActiveValue);

        // Game Data declared seperately
        gameDataPublisher.set(gameData);

        double periodTimeRemaining = periodTimeRemaining();
        periodTimePublisher.set(periodTimeRemaining);
    }

    /**
     * Initializes data only found when teleop mode is entered for simulation
     * purposes for Elastic in Robot.java.
     */
    public static void elasticTeleopInit() {
        if (RobotBase.isReal() && DriverStation.isDSAttached()) { // not in simulation
            gameData = DriverStation.getGameSpecificMessage();
        } else {
            gameData = ((Math.random() < 0.5) ? "R" : "B");
            DriverStationDataJNI.setGameSpecificMessage(gameData);
        }
    }

    /**
     * Cannot instantiate utility class.
     */
    private GamePeriod() {
        throw new UnsupportedOperationException("GamePeriod is a utility class and cannot be instantiated.");
    }
}