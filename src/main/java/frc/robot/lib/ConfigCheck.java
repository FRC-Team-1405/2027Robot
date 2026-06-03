package frc.robot.lib;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.hardware.TalonFX;

import edu.wpi.first.wpilibj.Alert;
import edu.wpi.first.wpilibj.Preferences;
import edu.wpi.first.wpilibj.Alert.AlertType;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.function.Supplier;

public final class ConfigCheck{
    private String key;
    private String check;
    private Alert alert;

    public ConfigCheck(String key, Supplier<String> value){
        this.key=key;
        this.check=ComputeCheck(value.get());
        this.alert=new Alert(key+" failed Configuration check", AlertType.kWarning);

        VerifyCheck();
    }

    public ConfigCheck(String key, TalonFX talon){
        this(key, () -> {
            var fx_cfg = new TalonFXConfiguration();
            talon.getConfigurator().refresh(fx_cfg);
            return fx_cfg.serialize();
        });
    }

    public void SaveCheck() {
        Preferences.setString(key, check);
        alert.set(false);
    }

    public void VerifyCheck() {
        String check = Preferences.getString(key, "");  
        alert.set( !this.check.equals(check) );
    } 

    private String ComputeCheck(String input) {
         try {
            // Create MessageDigest instance for MD5
            MessageDigest md = MessageDigest.getInstance("MD5");

            // Update the digest with the input string bytes
            md.update(input.getBytes());

            // Get the hash's bytes 
            byte[] bytes = md.digest();

            // Convert the bytes to a hexadecimal string
            StringBuilder sb = new StringBuilder();
            for (byte b : bytes) {
                sb.append(String.format("%02x", b));
            }

            return sb.toString();

        } catch (NoSuchAlgorithmException e) {
            return "";
        }
    }
}
