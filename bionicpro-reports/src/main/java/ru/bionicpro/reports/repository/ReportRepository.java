package ru.bionicpro.reports.repository;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import ru.bionicpro.reports.model.UserReport;

import java.util.List;
import java.util.Optional;

@Slf4j
@Repository
@RequiredArgsConstructor
public class ReportRepository {

    private final JdbcTemplate jdbcTemplate;

    // new

    private final RowMapper<UserReport> rowMapper = (rs, rowNum) -> {
        UserReport report = new UserReport();
        report.setUserId(rs.getString("user_id"));
        report.setUserName(rs.getString("user_name"));
        report.setEmail(rs.getString("email"));
        report.setPhone(rs.getString("phone"));
        report.setProsthesisModel(rs.getString("prosthesis_model"));
        report.setSerialNumber(rs.getString("serial_number"));
        report.setRegistrationDate(rs.getDate("registration_date") != null ?
                rs.getDate("registration_date").toLocalDate() : null);
        report.setTotalMovements(rs.getInt("total_movements"));
        report.setAvgReactionTime(rs.getDouble("avg_reaction_time"));
        report.setMedianReactionTime(rs.getDouble("median_reaction_time"));
        report.setMinReactionTime(rs.getInt("min_reaction_time"));
        report.setMaxReactionTime(rs.getInt("max_reaction_time"));
        report.setAvgSignalQuality(rs.getDouble("avg_signal_quality"));
        report.setMinSignalQuality(rs.getDouble("min_signal_quality"));
        report.setAvgBatteryLevel(rs.getInt("avg_battery_level"));
        report.setPerformanceScore(rs.getDouble("performance_score"));
        report.setNeedsCalibration(rs.getBoolean("needs_calibration"));
        report.setLastActiveDate(rs.getDate("last_active_date") != null ?
                rs.getDate("last_active_date").toLocalDate() : null);
        report.setUpdatedAt(rs.getTimestamp("updated_at") != null ?
                rs.getTimestamp("updated_at").toLocalDateTime() : null);
        return report;
    };

    /**
     * Поиск пользователя по ID
     * Сначала ищет в crm_users (CDC), затем в user_report_mart (телеметрия)
     */
    public Optional<UserReport> findById(String userId) {
        // 1. Получаем данные из CRM (CDC)
        String sqlCrm = """
                SELECT 
                    user_id,
                    full_name as user_name,
                    email,
                    phone,
                    prosthesis_model,
                    serial_number,
                    registration_date,
                    last_active_date,
                    created_at as updated_at
                FROM crm_users
                WHERE user_id = ?
                ORDER BY inserted_at DESC
                LIMIT 1
                """;

        UserReport crmData = null;
        try {
            crmData = jdbcTemplate.queryForObject(sqlCrm, (rs, rowNum) -> {
                UserReport report = new UserReport();
                report.setUserId(rs.getString("user_id"));
                report.setUserName(rs.getString("user_name"));
                report.setEmail(rs.getString("email"));
                report.setPhone(rs.getString("phone"));
                report.setProsthesisModel(rs.getString("prosthesis_model"));
                report.setSerialNumber(rs.getString("serial_number"));
                report.setRegistrationDate(rs.getDate("registration_date") != null ?
                        rs.getDate("registration_date").toLocalDate() : null);
                report.setLastActiveDate(rs.getDate("last_active_date") != null ?
                        rs.getDate("last_active_date").toLocalDate() : null);
                report.setUpdatedAt(rs.getTimestamp("updated_at") != null ?
                        rs.getTimestamp("updated_at").toLocalDateTime() : null);
                return report;
            }, userId);
            log.debug("Found user in crm_users: {}", userId);
        } catch (Exception e) {
            log.debug("User not found in crm_users: {}", userId);
        }

        // 2. Получаем данные телеметрии из user_report_mart
        String sqlTelemetry = """
                SELECT 
                    total_movements,
                    avg_reaction_time,
                    median_reaction_time,
                    min_reaction_time,
                    max_reaction_time,
                    avg_signal_quality,
                    min_signal_quality,
                    avg_battery_level,
                    performance_score,
                    needs_calibration
                FROM user_report_mart
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """;

        UserReport telemetryData = null;
        try {
            telemetryData = jdbcTemplate.queryForObject(sqlTelemetry, (rs, rowNum) -> {
                UserReport report = new UserReport();
                report.setTotalMovements(rs.getInt("total_movements"));
                report.setAvgReactionTime(rs.getDouble("avg_reaction_time"));
                report.setMedianReactionTime(rs.getDouble("median_reaction_time"));
                report.setMinReactionTime(rs.getInt("min_reaction_time"));
                report.setMaxReactionTime(rs.getInt("max_reaction_time"));
                report.setAvgSignalQuality(rs.getDouble("avg_signal_quality"));
                report.setMinSignalQuality(rs.getDouble("min_signal_quality"));
                report.setAvgBatteryLevel(rs.getInt("avg_battery_level"));
                report.setPerformanceScore(rs.getDouble("performance_score"));
                report.setNeedsCalibration(rs.getBoolean("needs_calibration"));
                return report;
            }, userId);
            log.debug("Found telemetry for user: {}", userId);
        } catch (Exception e) {
            log.debug("No telemetry data for user: {}", userId);
        }

        // 3. Объединяем данные
        if (crmData == null && telemetryData == null) {
            return Optional.empty();
        }

        UserReport result = new UserReport();
        if (crmData != null) {
            result.setUserId(crmData.getUserId());
            result.setUserName(crmData.getUserName());
            result.setEmail(crmData.getEmail());
            result.setPhone(crmData.getPhone());
            result.setProsthesisModel(crmData.getProsthesisModel());
            result.setSerialNumber(crmData.getSerialNumber());
            result.setRegistrationDate(crmData.getRegistrationDate());
            result.setLastActiveDate(crmData.getLastActiveDate());
            result.setUpdatedAt(crmData.getUpdatedAt());
        }

        if (telemetryData != null) {
            result.setTotalMovements(telemetryData.getTotalMovements());
            result.setAvgReactionTime(telemetryData.getAvgReactionTime());
            result.setMedianReactionTime(telemetryData.getMedianReactionTime());
            result.setMinReactionTime(telemetryData.getMinReactionTime());
            result.setMaxReactionTime(telemetryData.getMaxReactionTime());
            result.setAvgSignalQuality(telemetryData.getAvgSignalQuality());
            result.setMinSignalQuality(telemetryData.getMinSignalQuality());
            result.setAvgBatteryLevel(telemetryData.getAvgBatteryLevel());
            result.setPerformanceScore(telemetryData.getPerformanceScore());
            result.setNeedsCalibration(telemetryData.getNeedsCalibration());
        }

        return Optional.of(result);
    }

    /**
     * Получение всех пользователей из CRM
     */
    public List<UserReport> findAllCrmUsers() {
        String sql = """
                SELECT 
                    user_id,
                    full_name as user_name,
                    email,
                    phone,
                    prosthesis_model,
                    serial_number,
                    registration_date,
                    last_active_date,
                    created_at as updated_at
                FROM crm_users
                ORDER BY created_at DESC
                """;
        return jdbcTemplate.query(sql, (rs, rowNum) -> {
            UserReport report = new UserReport();
            report.setUserId(rs.getString("user_id"));
            report.setUserName(rs.getString("user_name"));
            report.setEmail(rs.getString("email"));
            report.setPhone(rs.getString("phone"));
            report.setProsthesisModel(rs.getString("prosthesis_model"));
            report.setSerialNumber(rs.getString("serial_number"));
            report.setRegistrationDate(rs.getDate("registration_date") != null ?
                    rs.getDate("registration_date").toLocalDate() : null);
            report.setLastActiveDate(rs.getDate("last_active_date") != null ?
                    rs.getDate("last_active_date").toLocalDate() : null);
            report.setUpdatedAt(rs.getTimestamp("updated_at") != null ?
                    rs.getTimestamp("updated_at").toLocalDateTime() : null);
            return report;
        });
    }

    /**
     * Получение всех пользователей с полными данными (CRM + телеметрия)
     */
    public List<UserReport> findAll() {
        String sql = """
                SELECT 
                    u.user_id,
                    u.full_name as user_name,
                    u.email,
                    u.phone,
                    u.prosthesis_model,
                    u.serial_number,
                    u.registration_date,
                    COALESCE(m.total_movements, 0) as total_movements,
                    COALESCE(m.avg_reaction_time, 0) as avg_reaction_time,
                    COALESCE(m.median_reaction_time, 0) as median_reaction_time,
                    COALESCE(m.min_reaction_time, 0) as min_reaction_time,
                    COALESCE(m.max_reaction_time, 0) as max_reaction_time,
                    COALESCE(m.avg_signal_quality, 0) as avg_signal_quality,
                    COALESCE(m.min_signal_quality, 0) as min_signal_quality,
                    COALESCE(m.avg_battery_level, 0) as avg_battery_level,
                    COALESCE(m.performance_score, 0) as performance_score,
                    COALESCE(m.needs_calibration, false) as needs_calibration,
                    u.last_active_date,
                    u.created_at as updated_at
                FROM crm_users u
                LEFT JOIN user_report_mart m ON u.user_id = m.user_id
                ORDER BY COALESCE(m.performance_score, 0) DESC
                """;
        return jdbcTemplate.query(sql, rowMapper);
    }

    /**
     * Топ пользователей по производительности
     */
    public List<UserReport> findTopPerformers(int limit) {
        String sql = """
                SELECT 
                    u.user_id,
                    u.full_name as user_name,
                    u.email,
                    u.phone,
                    u.prosthesis_model,
                    u.serial_number,
                    u.registration_date,
                    COALESCE(m.total_movements, 0) as total_movements,
                    COALESCE(m.avg_reaction_time, 0) as avg_reaction_time,
                    COALESCE(m.median_reaction_time, 0) as median_reaction_time,
                    COALESCE(m.min_reaction_time, 0) as min_reaction_time,
                    COALESCE(m.max_reaction_time, 0) as max_reaction_time,
                    COALESCE(m.avg_signal_quality, 0) as avg_signal_quality,
                    COALESCE(m.min_signal_quality, 0) as min_signal_quality,
                    COALESCE(m.avg_battery_level, 0) as avg_battery_level,
                    COALESCE(m.performance_score, 0) as performance_score,
                    COALESCE(m.needs_calibration, false) as needs_calibration,
                    u.last_active_date,
                    u.created_at as updated_at
                FROM crm_users u
                LEFT JOIN user_report_mart m ON u.user_id = m.user_id
                WHERE COALESCE(m.total_movements, 0) > 0
                ORDER BY COALESCE(m.performance_score, 0) DESC
                LIMIT ?
                """;
        return jdbcTemplate.query(sql, rowMapper, limit);
    }

    /**
     * Пользователи, требующие калибровки
     */
    public List<UserReport> findUsersNeedingCalibration() {
        String sql = """
                SELECT 
                    u.user_id,
                    u.full_name as user_name,
                    u.email,
                    u.phone,
                    u.prosthesis_model,
                    u.serial_number,
                    u.registration_date,
                    COALESCE(m.total_movements, 0) as total_movements,
                    COALESCE(m.avg_reaction_time, 0) as avg_reaction_time,
                    COALESCE(m.median_reaction_time, 0) as median_reaction_time,
                    COALESCE(m.min_reaction_time, 0) as min_reaction_time,
                    COALESCE(m.max_reaction_time, 0) as max_reaction_time,
                    COALESCE(m.avg_signal_quality, 0) as avg_signal_quality,
                    COALESCE(m.min_signal_quality, 0) as min_signal_quality,
                    COALESCE(m.avg_battery_level, 0) as avg_battery_level,
                    COALESCE(m.performance_score, 0) as performance_score,
                    m.needs_calibration,
                    u.last_active_date,
                    u.created_at as updated_at
                FROM crm_users u
                LEFT JOIN user_report_mart m ON u.user_id = m.user_id
                WHERE m.needs_calibration = true
                ORDER BY COALESCE(m.performance_score, 0) ASC
                """;
        return jdbcTemplate.query(sql, rowMapper);
    }

    /**
     * Проверка существования пользователя
     */
    public boolean existsByUserId(String userId) {
        String sql = "SELECT COUNT(*) FROM crm_users WHERE user_id = ?";
        try {
            Integer count = jdbcTemplate.queryForObject(sql, Integer.class, userId);
            return count != null && count > 0;
        } catch (Exception e) {
            log.error("Error checking existence for user: {}", userId, e);
            return false;
        }
    }

}
