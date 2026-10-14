<div dir="rtl">

# SIGNALFORGE — ورقة غش (صفحة وحدة)

**الفكرة:** بيانات خام (CSV) ← فحص جودة ← جداول نظيفة ← KPIs ← forecast ونموذج ← سيناريوهات "شو لو؟". وفي موقع بيحلل CSV بالمتصفح بدون رفع.

**المسار:**
`data/raw` ← **Bronze** (خام كنصوص + SHA-256) ← **Silver** (أنواع صحيحة، بدون تكرار) ← **Gold** (جداول تحليل + Parquet) ← Dashboard / Forecast / Model / Decision Room

**أهم الأوامر:** `signalforge demo-data` · `build` · `reconcile` · `report` · `train` · `dashboard` · `verify-raw` (للبيانات الحقيقية)

**التقنيات:** Python, SQL, DuckDB, Parquet, pandas, scikit-learn, Streamlit, Next.js, TypeScript, pytest, Vitest, Playwright, GitHub Actions, Vercel.

**أرقام مؤكدة (بيانات synthetic):** 37 فحص جودة (32 بيوقّفوا البناء) · 6 KPIs متحقَّق منها بحساب مستقل · 49 + 31 اختبار · نموذج التأخير PR-AUC 0.134 مقابل 0.116 (ضعيف) · forecast تعادل مع الـ baseline.

**الحدود (قلها بصراحة):**
- كل النتائج على بيانات synthetic. ما في بيانات حقيقية ولا استنتاجات سوق.
- النموذج ضعيف، والـ forecast تقريبًا متعادل مع طريقة بسيطة.
- Power BI توثيق فقط، ما في `.pbix`.
- demo للتعلّم والعرض، مش منتج جاهز للإنتاج.

**حكي 30 ثانية:**
"بنيت SIGNALFORGE: بياخد بيانات مبيعات خام، بيفحصها وبينظّفها، بيحسب مؤشرات الأداء وبيتأكد منها بحساب ثاني، وبيجرّب توقّعات وسيناريوهات. وفي موقع بتحلل فيه ملف CSV بالمتصفح بدون ما يطلع من جهازك. الـ demo على بيانات مولَّدة، والنموذج ضعيف وبقولها بصراحة."

</div>
