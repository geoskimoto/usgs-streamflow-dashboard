# Admin Authentication System

## Overview

The USGS Streamflow Dashboard now includes a secure admin authentication system that protects data management controls while keeping the main dashboard publicly accessible.

## Features

### Public Dashboard (🏞️ Dashboard Tab)
- **Always accessible** - No authentication required
- Interactive map with streamflow gauges
- Visualization tools and charts
- Display customization controls:
  - Map style selection
  - Plot sizing options
  - Year highlighting
  - Chart height adjustment

### Admin Panel (🔧 Admin Tab)
- **Authentication required** - Protected access only
- Data management controls:
  - Site loading limits (1-3000 sites)
  - Data refresh operations
  - Cache clearing
  - System status monitoring
- Administrative features:
  - Export functionality
  - Activity logging
  - System information display

## Authentication

### Default Credentials
- **Username:** `admin`
- **Password:** `admin123`

### Security Configuration
For production deployment, set environment variables:
```bash
export ADMIN_USERNAME="your_admin_username"
export ADMIN_PASSWORD_HASH="your_hashed_password"
export SECRET_KEY="your_secret_key_for_sessions"
```

### Password Security
- Passwords are hashed using SHA-256
- Sessions are managed securely with Flask-Login
- Admin access is session-based (persists until logout or browser close)

## Usage Instructions

### Accessing Admin Panel

1. **Navigate to Admin Tab**
   - Click the "🔧 Admin" tab in the main navigation
   - You'll see a login prompt if not authenticated

2. **Login Process**
   - Click "🔑 Login" button
   - Enter admin credentials in the modal
   - Click "Login" to authenticate
   - Modal closes automatically on successful login

3. **Admin Functions**
   - **Site Limit Control:** Adjust max sites loaded (1-3000)
   - **Data Refresh:** Update gauge data from USGS servers
   - **Clear Cache:** Remove cached data for fresh downloads
   - **System Status:** View database and system information
   - **Export Data:** Download current dataset
   - **Activity Log:** Monitor recent system activity

4. **Logout**
   - Click "🚪 Logout" button in admin panel header
   - Returns to login prompt immediately

### Public Dashboard Usage

- **No authentication needed** for main dashboard
- All visualization features remain fully accessible
- Filter and display controls work normally
- Map interactions and gauge selection available

## Technical Implementation

### Architecture
- **Flask-Login** for session management
- **Tab-based interface** with conditional rendering
- **SHA-256 password hashing** for security
- **Environment variable configuration** for production

### File Structure
```
app.py                          # Main application with authentication
requirements.txt               # Updated with flask-login dependency
```

### Security Features
- Passwords never stored in plain text
- Session-based authentication (not token-based for simplicity)
- Admin functions protected at callback level
- Environment variable override for production credentials

## Deployment Notes

### Development
- Default credentials work out of the box
- Session secret key is set to development default
- All features available for testing

### Production
- **MUST** set custom environment variables:
  - `ADMIN_USERNAME`: Your chosen admin username
  - `ADMIN_PASSWORD_HASH`: SHA-256 hash of your password
  - `SECRET_KEY`: Random secret key for session security
- Consider using a proper authentication system for multiple users
- Monitor admin activity logs regularly

### Password Hash Generation
To generate a password hash for production:

```python
import hashlib
password = "your_secure_password"
hash_value = hashlib.sha256(password.encode()).hexdigest()
print(f"Set ADMIN_PASSWORD_HASH={hash_value}")
```

## Benefits

1. **Security Without Complexity**
   - Protects admin functions
   - Maintains public accessibility
   - Simple login process

2. **User Experience**
   - Seamless navigation between public/admin areas
   - No disruption to existing dashboard users
   - Clear visual separation of functions

3. **Administrative Control**
   - Centralized data management
   - System monitoring capabilities
   - Audit trail through activity logs

4. **Production Ready**
   - Environment-based configuration
   - Secure session management
   - Scalable authentication pattern

## Troubleshooting

### Login Issues
- Verify username/password combination
- Check browser console for JavaScript errors
- Ensure Flask-Login is installed (`pip install flask-login`)

### Admin Access Problems
- Confirm authentication store is working
- Check that admin tab callback receives authenticated state
- Verify session secret key is set

### Data Management Issues
- Admin functions require authentication
- Check that database permissions allow write operations
- Verify USGS API access for data refresh operations

This authentication system provides a secure foundation for administrative access while maintaining the dashboard's public accessibility and user-friendly interface.