using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;
using System.Text.Json.Serialization;
using System;

namespace Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ReportsController : ControllerBase
{
    private readonly ILogger<ReportsController> _logger;

    public ReportsController(ILogger<ReportsController> logger)
    {
        _logger = logger;
    }

    [HttpGet]
    public IActionResult GetReports()
    {
        var user = User.Identity.Name;
        var roles = User.Claims
            .Where(c => c.Type == ClaimTypes.Role)
            .Select(c => c.Value)
            .ToList();

        if (!roles.Contains("prothetic_user"))
        {
            return Forbid();
        }

        var reports = new[]
        {
            new Report
            {
                Id = 1,
                Title = "Report #1",
                GeneratedAt = DateTime.UtcNow,
                Value = 1500.50m
            },
            new Report
            {
                Id = 2,
                Title = "Report #2",
                GeneratedAt = DateTime.UtcNow,
                Value = 2300.75m
            },
            new Report
            {
                Id = 3,
                Title = "Report #3",
                GeneratedAt = DateTime.UtcNow,
                Value = 1800.25m
            }
        };

        return Ok(new
        {
            user,
            reports
        });
    }
}

public class Report
{
    public int Id { get; set; }
    public string Title { get; set; }
    public DateTime GeneratedAt { get; set; }
    public decimal Value { get; set; }
}
