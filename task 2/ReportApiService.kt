// ReportApiService.kt
interface ReportApiService {
    @GET("/reports")
    suspend fun getReport(
        @Header("Authorization") token: String,
        @Query("start_date") startDate: String,
        @Query("end_date") endDate: String
    ): Response<ReportResponse>
}

// В Activity/Fragment
fun onGenerateReportClick() {
    val token = "Bearer ${getStoredAccessToken()}" // из хранилища
    val startDate = "2025-04-01"
    val endDate = "2025-04-07"

    CoroutineScope(Dispatchers.IO).launch {
        val response = reportApi.getReport(token, startDate, endDate)
        withContext(Dispatchers.Main) {
            if (response.isSuccessful) {
                val report = response.body()
                // Отобразить отчёт в новом экране или сохранить в PDF
                showReport(report)
            } else {
                showError("Не удалось загрузить отчёт: ${response.code()}")
            }
        }
    }
}