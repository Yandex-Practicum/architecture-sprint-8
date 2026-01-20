using System.Collections.Generic;
using System.Security.Claims;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authentication;

namespace WebApplication1.Authorize;

public class RoleClaimsTransformation : IClaimsTransformation
{
	public Task<ClaimsPrincipal> TransformAsync(ClaimsPrincipal principal)
	{
		var identity = principal.Identity as ClaimsIdentity;
		// when decoding the token with jwt.io roles is present under realm_access
		var realmAccessClaim = identity?.FindFirst("realm_access");
		if (realmAccessClaim != null)
		{
			var options = new JsonSerializerOptions
				{ PropertyNameCaseInsensitive = true }; // Ignore case when deserializing JSON

			// Deserialize the realm_access JSON to extract the roles
			var realmAccess = JsonSerializer.Deserialize<RealmAccess>(realmAccessClaim.Value, options);

			if (realmAccess?.Roles != null)
			{
				foreach (var role in realmAccess.Roles)
				{
					// Add each role as a Claim of type ClaimTypes.Role
					identity.AddClaim(new Claim(ClaimTypes.Role, role));
				}
			}
		}

		return Task.FromResult(principal);
	}

	public class RealmAccess
	{
		public List<string>? Roles { get; set; }
	} // one user can be assigned multiple roles
}