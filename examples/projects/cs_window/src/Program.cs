using System;
using System.Windows.Forms;
internal static class Program {
    [STAThread]
    static void Main() {
        Application.EnableVisualStyles();
        using var form = new Form { Text = "PCIDE", Width = 640, Height = 400 };
        form.Controls.Add(new Label { Text = "窗口已就绪", AutoSize = true, Left = 30, Top = 30 });
        Application.Run(form);
    }
}
