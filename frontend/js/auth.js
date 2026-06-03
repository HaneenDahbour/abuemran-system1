// js/auth.js

async function doLogin(username, password) {
  const btn = document.getElementById("login-btn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "جاري التحقق...";
  }
  try {
    const data = await API.login(username, password);
    if (data?.token) {
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      location.reload();
    } else {
      toast("اسم المستخدم أو كلمة المرور غير صحيحة", "error");
    }
  } catch (err) {
    toast(err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "تسجيل الدخول";
    }
  }
}

function doLogout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  location.reload();
}
