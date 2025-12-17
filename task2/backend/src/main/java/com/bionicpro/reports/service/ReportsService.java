package com.bionicpro.reports.service;

import com.bionicpro.reports.dto.ReportResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Service
public class ReportsService {

    private static final Logger logger = LoggerFactory.getLogger(ReportsService.class);
    private final JdbcTemplate jdbcTemplate;

    public ReportsService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * Получить отчёты по пользователю из витрины ClickHouse
     */
    public List<ReportResponse> getReportsByUserId(Long userId, LocalDate startDate, LocalDate endDate) {
        try {
        StringBuilder sql = new StringBuilder("""
            SELECT 
                user_id,
                email,
                first_name,
                last_name,
                prosthesis_id,
                report_date,
                total_actions,
                avg_response_time,
                max_response_time,
                min_response_time,
                grasp_count,
                release_count,
                flex_count,
                avg_battery_level,
                min_battery_level,
                total_usage_seconds,
                usage_hours,
                actions_per_hour,
                efficiency_score,
                order_date,
                status
            FROM reports_data_mart
            WHERE user_id = ?
            """);

        // Добавляем фильтры по датам, если они указаны
        if (startDate != null) {
            sql.append(" AND report_date >= ?");
        }
        if (endDate != null) {
            sql.append(" AND report_date <= ?");
        }
        
        sql.append(" ORDER BY report_date DESC");

        // Подготавливаем параметры
        List<Object> params = new java.util.ArrayList<>();
        params.add(userId);
        if (startDate != null) {
            params.add(startDate);
        }
        if (endDate != null) {
            params.add(endDate);
        }

            return jdbcTemplate.query(
                sql.toString(),
                params.toArray(),
                new ReportRowMapper()
            );
        } catch (Exception e) {
            logger.error("Ошибка при получении отчётов из ClickHouse для пользователя {}: {}", userId, e.getMessage(), e);
            // Возвращаем пустой список вместо ошибки, если ClickHouse недоступен
            return new ArrayList<>();
        }
    }

    /**
     * RowMapper для преобразования результатов запроса в ReportResponse
     */
    private static class ReportRowMapper implements RowMapper<ReportResponse> {
        @Override
        public ReportResponse mapRow(ResultSet rs, int rowNum) throws SQLException {
            ReportResponse report = new ReportResponse();
            
            report.setUserId(rs.getLong("user_id"));
            report.setEmail(rs.getString("email"));
            report.setFirstName(rs.getString("first_name"));
            report.setLastName(rs.getString("last_name"));
            report.setProsthesisId(rs.getString("prosthesis_id"));
            report.setReportDate(rs.getObject("report_date", LocalDate.class));
            
            report.setTotalActions(rs.getInt("total_actions"));
            report.setAvgResponseTime(rs.getDouble("avg_response_time"));
            report.setMaxResponseTime(rs.getDouble("max_response_time"));
            report.setMinResponseTime(rs.getDouble("min_response_time"));
            
            report.setGraspCount(rs.getInt("grasp_count"));
            report.setReleaseCount(rs.getInt("release_count"));
            report.setFlexCount(rs.getInt("flex_count"));
            
            report.setAvgBatteryLevel(rs.getDouble("avg_battery_level"));
            report.setMinBatteryLevel(rs.getDouble("min_battery_level"));
            
            report.setTotalUsageSeconds(rs.getInt("total_usage_seconds"));
            report.setUsageHours(rs.getDouble("usage_hours"));
            report.setActionsPerHour(rs.getDouble("actions_per_hour"));
            report.setEfficiencyScore(rs.getDouble("efficiency_score"));
            
            report.setOrderDate(rs.getObject("order_date", LocalDate.class));
            report.setStatus(rs.getString("status"));
            
            return report;
        }
    }
}

